#!/usr/bin/env python3
"""Shared helpers of the backlinks-check skill.

Built on the DataForSEO client of the semantics-travel skill (sp_common: load_auth, api, journal_add) - the client is
imported, not copied.  This module adds what donor checks need: a per-domain cache with TTL, a cost ledger, a hard
budget with a reserve, a retry on gateway errors, the SERP task queue, the balance and the request plan used both by
the estimate (dry-run) and by the stages.

Nothing here prints credentials.  Layout (workdir = the backlinks folder):
  cache/<domain>/<endpoint>-<YYYY-MM-DD>.json   raw API answers (git-ignored), TTL 30 days, cache first
  runs/<run>/                                   input.json, stage0..2.json, pages.json, site-notes.json, verdicts.json,
                                                ledger.json, balance.log
"""
import argparse, datetime, glob, hashlib, json, os, re, statistics, sys, time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
SEMANTICS_SCRIPTS = os.path.join(os.path.dirname(SKILL_DIR), "semantics-travel", "scripts")
if not os.path.exists(os.path.join(SEMANTICS_SCRIPTS, "sp_common.py")):
    sys.exit(f"backlinks-check потребує скіл semantics-travel: не знайдено {SEMANTICS_SCRIPTS}\\sp_common.py")
sys.path.insert(0, SEMANTICS_SCRIPTS)
import sp_common as sp  # noqa: E402

CFG = json.load(open(os.path.join(SCRIPTS, "markets.json"), encoding="utf-8"))
PRICES = json.load(open(os.path.join(SCRIPTS, "prices.json"), encoding="utf-8"))
RESERVE = PRICES["reserve"]
TTL_DAYS = 30
JOURNAL_SECTION = "backlinks-check"
VERDICTS = ["сильний", "середній", "слабкий"]
RISK = [(n, re.compile(rx, re.I)) for n, rx in CFG["risk"]]
NEWS = re.compile(CFG["news_words"], re.I)
CASINO_BRAND = re.compile(CFG["casino_brand"], re.I)
SOCIAL = set(CFG["social_domains"])
SECOND_LEVEL = {"com.ua", "in.ua", "org.ua", "net.ua", "kiev.ua", "co.uk", "gov.ua", "edu.ua", "lviv.ua", "rv.ua", "vn.ua", "pl.ua", "mk.ua", "sumy.ua", "lutsk.ua",
                "volyn.ua", "ks.ua", "te.ua", "cv.ua", "if.ua", "km.ua", "od.ua", "dp.ua", "kh.ua", "zp.ua", "ck.ua", "cn.ua", "kr.ua", "uz.ua", "biz.ua", "kherson.ua",
                "com.kz", "org.kz", "edu.kz", "gov.kz", "com.br", "co.in", "ac.id"}


class BudgetStop(SystemExit):
    pass


# ---------- small helpers ----------
def norm_domain(s):
    s = (s or "").strip().lower()
    s = re.sub(r"^[a-z]+://", "", s).split("/")[0].split("?")[0].split(":")[0]
    return re.sub(r"^www\.", "", s).strip(".")


def reg_domain(host):
    p = norm_domain(host).split(".")
    return ".".join(p[-3:]) if len(p) >= 3 and ".".join(p[-2:]) in SECOND_LEVEL else ".".join(p[-2:])


def find_market(name):
    n = (name or "").strip().lower()
    for code, m in CFG["markets"].items():
        if n in m["names"]:
            return code, m
    sys.exit(f"Невідомий ринок «{name}». Відомі: {', '.join(m['names'][0] for m in CFG['markets'].values())}. Додай ринок у scripts\\markets.json "
             f"(location_code, se_domain, мови, TLD, запити SERP) і перевір його в довіднику Labs.")


def is_market_tld(domain, market):
    return any(domain.endswith(t) for t in market["tlds"])


def niche(text):
    for n, rx in RISK:
        if rx.search(text or ""):
            return n
    return ""


def price(key, rows=None):
    p = PRICES["endpoints"][key]
    return round(p["base"] + p.get("per_row", 0) * (p["rows"] if rows is None else rows), 6)


def pct(a, b):
    return (b - a) / a * 100 if a else None


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def fmt_money(v):
    return f"{v:.4f}".replace(".", ",")


def parser(desc):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--workdir", default=".", help="папка backlinks (там cache, runs, donors-*.xlsx, CLAUDE.md)")
    ap.add_argument("--run", default=None, help="назва запуску: runs/<run>/ у робочій папці, напр. poehalisnami-kz-2026-10-08")
    ap.add_argument("--cache-dir", default=None, help="інша папка кешу (тести: tests/fixtures/<...>/cache)")
    ap.add_argument("--offline", action="store_true", help="лише кеш, без запитів і без урахування TTL")
    ap.add_argument("--yes", action="store_true", help="виконати платні запити; без нього - лише кошторис")
    ap.add_argument("--today", default=None, help="дата запуску YYYY-MM-DD (за замовчуванням сьогодні)")
    return ap


# ---------- a run: files, cache, ledger, budget ----------
class Run:
    def __init__(self, a):
        self.workdir = os.path.abspath(a.workdir)
        self.dir = a.run if os.path.isabs(a.run) else os.path.join(self.workdir, "runs", a.run)
        self.name = os.path.basename(self.dir.rstrip("/\\"))
        self.cache = os.path.abspath(a.cache_dir) if a.cache_dir else os.path.join(self.workdir, "cache")
        self.offline, self.yes = a.offline, a.yes
        self.today = a.today or datetime.date.today().isoformat()
        os.makedirs(self.dir, exist_ok=True)
        self.hits, self.missing, self._auth = {}, [], None
        self.input = self.load("input.json") or {}
        self.budget = float(self.input.get("budget") or 0)
        self.market_code = self.input.get("market")
        self.market = CFG["markets"].get(self.market_code) if self.market_code else None

    # files of the run
    def path(self, name):
        return os.path.join(self.dir, name)

    def load(self, name, default=None):
        p = self.path(name)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

    def save(self, name, obj):
        json.dump(obj, open(self.path(name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ledger and budget
    def ledger(self):
        return self.load("ledger.json", [])

    def spent(self):
        return sum(r["cost"] for r in self.ledger())

    def log_cost(self, stage, domain, endpoint, pkey, est, cost, status, n=1):
        L = self.ledger()
        L.append({"stage": stage, "domain": domain, "endpoint": endpoint, "price_key": pkey, "requests": n, "est": round(est, 6), "cost": round(float(cost or 0), 6),
                  "status": status, "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
        self.save("ledger.json", L)

    def check_budget(self, est, what):
        need = self.spent() + est * (1 + RESERVE)
        if self.budget and need > self.budget + 1e-9:
            raise BudgetStop(f"СТОП до запиту «{what}»: витрачено {self.spent():.4f} $ + прогноз {est * (1 + RESERVE):.4f} $ (із запасом {int(RESERVE * 100)}%) "
                             f"= {need:.4f} $ > бюджет {self.budget:.2f} $.\nЩо можна зрізати: не брати historical_rank_overview і ranked_keywords для загальних доменів "
                             f"(вже так за замовчуванням), зменшити кількість кандидатів (--candidates), не робити точкову перевірку зони.")

    def auth(self):
        if self._auth is None:
            self._auth = sp.load_auth()
        return self._auth

    # cache
    def cached(self, domain, endpoint):
        """Newest cache file for domain/endpoint; older than TTL counts as missing (TTL is ignored offline)."""
        best = None
        for f in glob.glob(os.path.join(self.cache, domain, f"{endpoint}-????-??-??.json")):
            if best is None or os.path.basename(f) > os.path.basename(best):
                best = f
        if best and not self.offline:
            age = (datetime.date.fromisoformat(self.today) - datetime.date.fromisoformat(os.path.basename(best)[-15:-5])).days
            if age > TTL_DAYS:
                return None
        return best

    def read(self, domain, endpoint):
        f = self.cached(domain, endpoint)
        if f:
            self.hits[endpoint] = self.hits.get(endpoint, 0) + 1
            return json.load(open(f, encoding="utf-8"))
        return None

    def write(self, domain, endpoint, resp):
        p = os.path.join(self.cache, domain, f"{endpoint}-{self.today}.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(resp, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return p

    def api(self, path, body, method="POST"):
        """One API call with a retry on gateway errors (an HTTP 5xx answer normally costs nothing, but the balance is the judge)."""
        last = None
        for attempt in range(3):
            try:
                return sp.api(self.auth(), path, body, method=method)
            except Exception as e:  # urllib HTTPError / URLError
                last = e
                print(f"  помилка HTTP ({path}), спроба {attempt + 1}/3: {e}")
                time.sleep(8)
        print(f"  запит не вдався: {path}: {last}")
        return None

    def call(self, stage, domain, endpoint, path, body, pkey, rows=None, method="POST"):
        """Cache first; otherwise a paid request (needs --yes, respects the budget). Returns the parsed answer or None."""
        r = self.read(domain, endpoint)
        if r is not None:
            return r
        if self.offline or not self.yes:
            self.missing.append((domain, endpoint, pkey, rows))
            return None
        est = price(pkey, rows)
        self.check_budget(est, f"{endpoint} {domain}")
        r = self.api(path, [body] if body is not None else None, method=method)
        if r is None:
            self.log_cost(stage, domain, endpoint, pkey, est, 0, "http_error")
            return None
        t = (r.get("tasks") or [{}])[0] or {}
        status = t.get("status_code") or r.get("status_code")
        self.log_cost(stage, domain, endpoint, pkey, est, r.get("cost"), status)
        if status != 20000:
            print(f"  помилка API {endpoint} {domain}: {status} {t.get('status_message') or r.get('status_message')}")
            self.write(domain, endpoint + "-error", r)
            return None
        self.write(domain, endpoint, r)
        return r

    def balance(self, label):
        """Account balance from appendix/user_data (free); logged to balance.log. Skipped offline."""
        if self.offline:
            return None
        r = self.api("appendix/user_data", None, method="GET")
        if not r:
            return None
        bal = r["tasks"][0]["result"][0]["money"].get("balance")
        with open(self.path("balance.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "balance": bal}) + "\n")
        return bal

    def balances(self):
        p = self.path("balance.log")
        return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def result(r):
    try:
        return (r["tasks"][0]["result"] or [{}])[0] or {}
    except Exception:
        return {}


# ---------- endpoint names ----------
def ep_overview(run, lang):
    return f"labs-domain_rank_overview-{run.market_code}-{lang}"


def ep_hist(run, lang):
    return f"labs-historical_rank_overview-{run.market_code}-{lang}"


def ep_ranked(run, lang):
    return f"labs-ranked_keywords-{run.market_code}-{lang}"


def ep_zone(zone):
    return "backlinks-referring_domains-" + re.sub(r"[^a-z0-9]", "", zone)


EP_ALL = "labs-domain_rank_overview-all"
EP_SUMMARY = "backlinks-summary"
EP_SPAM = "backlinks-bulk_spam_score"
EP_REF = "backlinks-referring_domains"
EP_TS = "backlinks-timeseries_summary"
EP_LINK = "backlinks-backlinks-to-acceptor"
EP_LANGS = "labs-locations_and_languages"


def spam_scores(run):
    """Spam scores from every cached bulk answer (they are stored under _list* pseudo-domains)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(run.cache, "_list*", f"{EP_SPAM}-????-??-??.json"))):
        for i in result(json.load(open(f, encoding="utf-8"))).get("items") or []:
            out[i["target"]] = i.get("spam_score")
    return out


def labs_languages(run):
    """Languages Labs supports for the market location; {} when the reference list is not cached."""
    f = run.cached("_labs", EP_LANGS)
    if not f:
        return None, {}
    locs = json.load(open(f, encoding="utf-8"))["tasks"][0]["result"]
    names = {l.get("location_code"): l.get("location_name") for l in locs}
    hit = [l for l in locs if l.get("location_code") == run.market["location_code"]]
    return ([x.get("language_code") for x in (hit[0].get("available_languages") or [])] if hit else []), names


def market_langs(run):
    s0 = run.load("stage0.json") or {}
    return s0.get("languages") or run.market["languages"]


def acceptor_hits(run, domains):
    """Donors of the acceptor that belong to the checked domains (local filter, no regex filter in the API)."""
    r = run.read(run.input["acceptor"], EP_REF)
    if r is None:
        return None, None
    res = result(r)
    items = res.get("items") or []
    hits = {}
    for i in items:
        for d in domains:
            if i["domain"] == d or i["domain"].endswith("." + d):
                hits.setdefault(d, []).append({"domain": i["domain"], "rank": i.get("rank"), "backlinks": i.get("backlinks"), "first_seen": (i.get("first_seen") or "")[:10]})
    info = {"total": res.get("total_count"), "returned": len(items), "rank_gt0": sum(1 for i in items if (i.get("rank") or 0) > 0)}
    return hits, info


def spam_zone(summary_item):
    """A free-hosting zone that gives at least 40 % of backlinks (a sign of doorway spam or of a network)."""
    tld = summary_item.get("referring_links_tld") or {}
    total = summary_item.get("backlinks") or 0
    for z, n in tld.items():
        if z in CFG["free_hosting_zones"] and total and n / total >= 0.4:
            return z, n
    return None, 0


# ---------- request plan (dry-run estimate and "what is missing in the cache") ----------
def plan_stage1(run):
    doms = [d["domain"] for d in run.input["domains"]]
    langs = market_langs(run)
    P = []

    def add(domain, endpoint, pkey, rows=None, note=""):
        P.append({"stage": "1", "domain": domain, "endpoint": endpoint, "price_key": pkey, "rows": rows, "cached": bool(run.cached(domain, endpoint)), "est": price(pkey, rows), "note": note})
    sc = spam_scores(run)
    miss = [d for d in doms if d not in sc]
    P.append({"stage": "1", "domain": "_list", "endpoint": EP_SPAM, "price_key": "backlinks_bulk_spam_score", "rows": len(miss) or len(doms), "cached": not miss,
              "est": price("backlinks_bulk_spam_score", len(miss) or len(doms)), "note": f"один запит на {len(miss) or len(doms)} доменів"})
    for d in doms:
        add(d, EP_SUMMARY, "backlinks_summary")
        for lg in langs:
            add(d, ep_overview(run, lg), "labs_domain_rank_overview")
        if not is_market_tld(d, run.market):
            add(d, EP_ALL, "labs_domain_rank_overview_all", note="без location: усі ринки Labs")
        for q in run.market["queries"]:
            add(d, f"serp-organic-task-{q}", "serp_task")
    acc = run.input["acceptor"]
    add(acc, EP_REF, "backlinks_referring_domains", 1000, "донори акцептора, limit 1000 за рангом")
    hits, _ = acceptor_hits(run, doms)
    run.hits.pop(EP_REF, None)
    if hits is None:
        add("(домен, що вже посилається)", EP_LINK, "backlinks_backlinks", 1, "резерв: лише якщо хтось зі списку вже посилається")
    else:
        for d in hits:
            add(d, EP_LINK, "backlinks_backlinks", 1, "деталі наявного посилання")
    return P


def assumed_candidates(run):
    """Before stage 1 the candidates are unknown: N+1 domains, market-TLD domains first."""
    doms = [d["domain"] for d in run.input["domains"]]
    n = min(len(doms), int(run.input["recommend"]) + 1)
    tld = [d for d in doms if is_market_tld(d, run.market)]
    return (tld + [d for d in doms if d not in tld])[:n]


def plan_stage2(run, candidates=None):
    s1 = run.load("stage1.json") or {}
    cands = candidates or s1.get("candidates") or s1.get("candidates_auto") or assumed_candidates(run)
    langs = market_langs(run)
    P = []

    def add(domain, endpoint, pkey, rows=None, note=""):
        P.append({"stage": "2", "domain": domain, "endpoint": endpoint, "price_key": pkey, "rows": rows, "cached": bool(run.cached(domain, endpoint)), "est": price(pkey, rows), "note": note})
    zone_reserved = False
    for d in cands:
        add(d, EP_TS, "backlinks_timeseries_summary")
        add(d, EP_REF, "backlinks_referring_domains", 100, "топ-100 донорів за рангом")
        if is_market_tld(d, run.market):
            lg = ((s1.get("domains") or {}).get(d) or {}).get("dominant_lang") or langs[0]
            add(d, ep_hist(run, lg), "labs_historical_rank_overview")
            add(d, ep_ranked(run, lg), "labs_ranked_keywords", 100)
        f = run.cached(d, EP_SUMMARY)
        if f:
            z, _ = spam_zone(result(json.load(open(f, encoding="utf-8"))))
            if z:
                add(d, ep_zone(z), "backlinks_referring_domains", 30, f"точкова перевірка зони {z}")
        elif not zone_reserved:
            zone_reserved = True
            add("(кандидат зі спам-зоною)", "backlinks-referring_domains-<зона>", "backlinks_referring_domains", 30, "резерв: точкова перевірка зони, якщо знайдеться")
    return P, cands


def print_plan(P, budget=None, spent=0.0, show_missing=False):
    """Prints the plan grouped by stage and endpoint; returns (cost without reserve, cost with reserve) of what is not cached."""
    groups = {}
    for p in P:
        key = (p["stage"], re.sub(r"^(serp-organic-task)-.*", r"\1 (3 запити на домен)", p["endpoint"]))
        g = groups.setdefault(key, [0, 0, 0.0])
        g[0] += 1
        g[1] += 1 if p["cached"] else 0
        g[2] += 0 if p["cached"] else p["est"]
    print(f"{'етап':<5} {'ендпоінт':<52} {'усього':>6} {'з кешу':>7} {'запитати':>9} {'прогноз, $':>11}")
    tot = {}
    for (st, ep), (n, c, cost) in groups.items():
        print(f"{st:<5} {ep:<52} {n:>6} {c:>7} {n - c:>9} {cost:>11.4f}")
        tot[st] = tot.get(st, 0.0) + cost
    total = sum(tot.values())
    for st in sorted(tot):
        print(f"  етап {st}: {tot[st]:.4f} $ без запасу, {tot[st] * (1 + RESERVE):.4f} $ із запасом {int(RESERVE * 100)}%")
    print(f"  РАЗОМ до запиту: {total:.4f} $ без запасу, {total * (1 + RESERVE):.4f} $ із запасом {int(RESERVE * 100)}% (ціни станом на {PRICES['date']})")
    if budget:
        left = budget - spent - total * (1 + RESERVE)
        print(f"  бюджет {budget:.2f} $, уже витрачено {spent:.4f} $, після запитів залишиться {left:.4f} $" + ("" if left >= 0 else "  <-- ПЕРЕВИЩЕННЯ: зупинитися до запиту"))
    if show_missing:
        miss = [p for p in P if not p["cached"]]
        print(f"  бракує в кеші: {len(miss)} файлів")
        for p in miss:
            print(f"    {p['domain']:<30} {p['endpoint']:<46} {p['est']:.4f} $  {p['note']}")
    return total, total * (1 + RESERVE)


# ---------- SERP through the task queue ----------
def serp_tasks(run, stage="1"):
    """Posts missing site: queries to the queue, waits, stores each answer in the cache. Returns {domain: {query: state}}."""
    m = run.market
    doms = [d["domain"] for d in run.input["domains"]]
    ids = run.load("serp_ids.json", {})
    todo = [(d, q) for d in doms for q in m["queries"] if not run.cached(d, f"serp-organic-task-{q}") and f"{d}|{q}" not in ids]
    if todo and not run.offline and run.yes:
        est = len(todo) * price("serp_task")
        run.check_budget(est, f"SERP task_post x{len(todo)}")
        body = [{"keyword": f"site:{d} {m['queries'][q]}", "location_code": m["location_code"], "language_code": m["serp_language"], "se_domain": m["se_domain"],
                 "depth": 10, "tag": f"{d}|{q}"} for d, q in todo]
        r = run.api("serp/google/organic/task_post", body)
        if r:
            run.log_cost(stage, "_list", "serp-organic-task_post", "serp_task", est, r.get("cost"), r.get("status_code"), n=len(todo))
            for t in r.get("tasks") or []:
                if t.get("status_code") == 20100:
                    ids[t["data"]["tag"]] = t["id"]
            run.save("serp_ids.json", ids)
    elif todo:
        for d, q in todo:
            run.missing.append((d, f"serp-organic-task-{q}", "serp_task", None))
    if not run.offline and run.yes:
        for attempt in range(30):
            pend = [(tag, i) for tag, i in ids.items() if not run.cached(tag.split("|")[0], f"serp-organic-task-{tag.split('|')[1]}")]
            if not pend:
                break
            time.sleep(12)
            for tag, i in pend:
                d, q = tag.split("|")
                r = run.api("serp/google/organic/task_get/advanced/" + i, None, method="GET")
                t = ((r or {}).get("tasks") or [{}])[0]
                if t.get("status_code") == 20000 and t.get("result"):
                    run.write(d, f"serp-organic-task-{q}", r)
    out = {}
    for d in doms:
        out[d] = {}
        for q in m["queries"]:
            r = run.read(d, f"serp-organic-task-{q}")
            if r is None:
                out[d][q] = {"state": "не отримано", "count": None, "organic": 0, "own": []}
                continue
            res = result(r)
            org = [i for i in (res.get("items") or []) if i.get("type") == "organic"]
            own = [{"url": i["url"], "title": i.get("title") or "", "descr": (i.get("description") or "")[:200]} for i in org if (i.get("domain") or "").endswith(d)]
            state = "ok" if own else ("невизначено" if org else "0 результатів")
            out[d][q] = {"state": state, "count": res.get("se_results_count"), "organic": len(org), "own": own}
    return out


def is_risky_pr(item, wanted):
    """A search result that looks like a paid article of the wanted niche (not a news story about the niche)."""
    text = item["title"] + " " + item["url"]
    return niche(text) == wanted and not NEWS.search(text + " " + item.get("descr", ""))
