#!/usr/bin/env python3
"""Step b: on-page analysis of the confirmed competitor pages and of the own page.

python analyze_competitors.py --workdir . --page <URL> [--refresh] [--offline]

Pages are rendered with render_page.py of the claude-seo plugin (free).  Rendered HTML is cached in competitors-raw/,
so a repeated run costs nothing; --offline never touches the network (a page that is not cached counts as not opened).
A page that answers 4xx/5xx or shows a consent wall is "not opened": the next reserve URL takes its place and the
replacement with its reason is recorded.  The own page is rendered with a browser User-Agent through the plugin's
render_page(); if that import breaks, the script stops instead of going on without the own page.
Page content is untrusted data: it is parsed, never executed.  Output: competitors-<slug>.json.
"""
import argparse, glob, json, os, re, shutil, statistics, subprocess, sys
from collections import Counter
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

import tz_common as tz

OWN_SNIPPET = ("import sys, json; sys.path.insert(0, sys.argv[1]); from render_page import render_page; "
               "sys.stdout.reconfigure(encoding='utf-8'); "
               "print(json.dumps(render_page(sys.argv[2], mode='always', timeout_ms=int(sys.argv[4]), user_agent=sys.argv[3]), default=str))")


def plugin_scripts():
    env = os.environ.get("CLAUDE_SEO_SCRIPTS")
    cands = [env] if env else sorted(glob.glob(os.path.expanduser(r"~/.claude/plugins/cache/*claude-seo*/claude-seo/*/scripts")), reverse=True)
    for c in cands:
        if c and os.path.exists(os.path.join(c, "render_page.py")):
            return c
    tz.die("не знайдено render_page.py плагіна claude-seo (~/.claude/plugins/cache/*claude-seo*/claude-seo/<версія>/scripts). "
           "Встановіть плагін або задайте шлях у змінній CLAUDE_SEO_SCRIPTS.")


def plugin_python():
    p = os.path.join(os.environ.get("CLAUDE_SEO_DATA_DIR") or os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")), "claude-seo"),
                     ".venv", "Scripts" if sys.platform == "win32" else "bin", "python.exe" if sys.platform == "win32" else "python")
    return p if os.path.exists(p) else None


# key-like strings of third-party pages never reach the cache (and the repository): Google keys, GitHub/OpenAI/Slack/AWS/Stripe tokens
SECRET_RX = re.compile(r"(?<![\w-])(?:AIza[0-9A-Za-z_\-]{35}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
                       r"|sk-(?:ant-|proj-)?[A-Za-z0-9_]{32,}|xox[baprs]-[A-Za-z0-9\-]{20,}|AKIA[0-9A-Z]{16}|[sr]k_live_[0-9A-Za-z]{16,})")   # not CSS classes like "desk-module-…"


def redact(d):
    return json.loads(SECRET_RX.sub("<REDACTED>", json.dumps(d, ensure_ascii=False, default=str)))


class Renderer:
    def __init__(self, ctx, refresh, offline):
        self.ctx, self.refresh, self.offline, self.raw = ctx, refresh, offline, ctx["f"]["raw"]
        os.makedirs(self.raw, exist_ok=True)
        self.scripts = None

    def get(self, url, mode, own=False):
        cache = tz.cache_file(self.raw, url, mode)
        if os.path.exists(cache) and not self.refresh:
            return tz.rjson(cache)
        if self.offline:
            return {"url": url, "error": "не в кеші competitors-raw/ (режим --offline, мережа не використовується)", "content": None, "offline_miss": True}
        self.scripts = self.scripts or plugin_scripts()
        cfg = self.ctx["cfg"]
        if own:
            py = plugin_python()
            if not py:
                tz.die("не знайдено Python плагіна claude-seo (.venv): власну сторінку нема чим відкрити з браузерним User-Agent. Запустіть setup плагіна.")
            cmd = [py, "-c", OWN_SNIPPET, self.scripts, url, cfg["browser_user_agent"], str(cfg["render_timeout_ms"])]
        else:
            bash = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"   # the plugin launcher is a shell script
            cmd = [bash, os.path.join(self.scripts, "claude-seo").replace("\\", "/"), "run", "render_page.py", "--json", "--mode", mode,
                   "--timeout-ms", str(cfg["render_timeout_ms"]), url]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=300)
            out, err = (r.stdout or b"").decode("utf-8", "replace"), (r.stderr or b"").decode("utf-8", "replace")
            if own and ("ImportError" in err or "TypeError" in err or "{" not in out):
                tz.die("виклик render_page() плагіна claude-seo для власної сторінки не спрацював (після оновлення плагіна змінився інтерфейс?). "
                       "Аналіз зупинено, щоб не збирати ТЗ без власної сторінки.\n" + err[-600:])
            d = json.loads(out[out.index("{"):])
        except SystemExit:
            raise
        except Exception as e:  # reported, not hidden
            if own:
                tz.die(f"власну сторінку не вдалося відрендерити: {type(e).__name__}: {str(e)[:300]}")
            d = {"url": url, "error": f"render failed: {type(e).__name__}: {str(e)[:200]}", "content": None}
        d.pop("raw_content", None)
        d.pop("accessibility_tree", None)
        d = redact(d)
        tz.wjson(cache, d)
        return d


def make_parser(ctx):
    S, T, cfg = ctx["S"], ctx["T"], ctx["cfg"]
    pat = {k: re.compile(v, re.I) for k, v in T["patterns"].items()}
    months = T["months"]
    season_re = re.compile(T["patterns"]["season"] + "|" + "|".join(m.lower() for m in months), re.I)
    ents = list(T.get("entities", {}).get(S["slug"], [])) or [n.capitalize() for n in (S.get("regions") or {})]
    block_ents = ents[:T.get("region_block_entities", len(ents))]
    keywords = [k["keyword"] for k in ctx["keys"]]
    own_excl = [re.compile(x, re.I) for x in cfg["own_text_exclude"]]

    def is_boiler(el):
        for p in [el] + list(el.parents):
            if p.name in ("nav", "header", "footer", "aside", "form"):
                return True
            attrs = " ".join([p.get("id") or ""] + (p.get("class") or []) + [p.get("role") or ""]) if hasattr(p, "get") else ""
            if attrs and p.name not in ("body", "html", "main") and pat["boilerplate"].search(attrs):
                return True
        return False

    def jsonld(soup):
        types, faq_q, rating = set(), [], None
        for s in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
            try:
                data = json.loads(s.string or s.get_text() or "")
            except Exception:
                continue
            stack = [data]
            while stack:
                v = stack.pop()
                if isinstance(v, dict):
                    t = v.get("@type")
                    for x in (t if isinstance(t, list) else [t]):
                        if isinstance(x, str):
                            types.add(x)
                    if v.get("@type") == "Question" and v.get("name"):
                        faq_q.append(tz.norm(str(v["name"])))
                    if v.get("@type") == "AggregateRating":
                        rating = {k: v.get(k) for k in ("ratingValue", "reviewCount", "ratingCount", "bestRating") if v.get(k) is not None}
                    stack.extend(v.values())
                elif isinstance(v, list):
                    stack.extend(v)
        return sorted(types), faq_q, rating

    def kw_presence(kw, zones):
        res = {z: tz.exact_count(kw, t) for z, t in zones.items()}
        toks = [t for t in re.findall(r"\w+", kw.lower()) if t not in T["term_glue"]]
        sents = re.split(r"(?<=[.!?])\s+|\n+", zones["text"].lower())
        res["all_words_in_sentence"] = sum(1 for s in sents if all(re.search(r"(?<!\w)" + re.escape(t), s) for t in toks))
        return res

    def parse(url, d, own=False):
        html = d.get("content") or ""
        res = {"url": url, "final_url": d.get("url"), "status": d.get("status_code"), "mode_used": d.get("mode_used"), "error": d.get("error"), "ok": False}
        if not html:
            res["fail_reason"] = d.get("error") or "порожня відповідь"
            return res
        soup = BeautifulSoup(html, "html.parser")
        types, faq_ld, rating = jsonld(soup)
        title = tz.norm(soup.title.get_text()) if soup.title else ""
        md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        desc = tz.norm(md.get("content")) if md else ""
        canon = soup.find("link", rel=lambda v: v and "canonical" in v)
        robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
        for t in soup(["script", "style", "noscript", "svg", "template"]):
            t.decompose()
        body = soup.body or soup
        full_text = tz.norm(body.get_text(" "))
        h1 = [tz.norm(h.get_text(" ")) for h in body.find_all("h1") if tz.norm(h.get_text(" "))]
        outline = [{"level": h.name, "text": tz.norm(h.get_text(" "))[:200]} for h in body.find_all(["h2", "h3"])
                   if tz.norm(h.get_text(" ")) and not is_boiler(h)]
        # main text: block-level units outside navigation/boilerplate; offer cards with short strings are dropped
        blocks, seen, ui = [], set(), []
        for el in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "dd", "dt", "blockquote", "summary", "div", "span"]):
            if el.name in ("div", "span"):
                t = tz.norm(" ".join(c for c in el.find_all(string=True, recursive=False)))
                if len(t) < 80:
                    continue
            else:
                if el.name in ("li", "td", "dd") and el.find(["p", "li", "h2", "h3", "h4"]):
                    continue
                t = tz.norm(el.get_text(" "))
                if len(t) < (1 if el.name in ("h1", "h2", "h3", "h4", "summary") else 40):
                    continue
            if t in seen or is_boiler(el):
                continue
            seen.add(t)
            if own and any(x.search(t) for x in own_excl):
                ui.append(t)
                continue
            blocks.append((el.name, t))
        heads = ("h1", "h2", "h3", "h4")
        main_text = "\n".join(("\n## " + t if n in heads else t) for n, t in blocks)
        body_text = "\n".join(t for n, t in blocks if n not in heads)

        lists = []
        for l in body.find_all(["ul", "ol"]):
            if is_boiler(l):
                continue
            lis = l.find_all("li", recursive=False)
            txt = tz.norm(l.get_text(" "))
            if len(lis) < 2 or len(txt) < 80:
                continue
            linked = sum(len(tz.norm(x.get_text(" "))) for x in l.find_all("a"))
            lists.append({"items": len(lis), "kind": "link-list" if linked > 0.7 * len(txt) else "content", "sample": tz.norm(lis[0].get_text(" "))[:90]})
        tables = []
        for t in body.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) >= 2:
                tables.append({"rows": len(rows), "header": [tz.norm(c.get_text(" "))[:40] for c in rows[0].find_all(["th", "td"])][:8],
                               "first_col": [tz.norm(r.find(["th", "td"]).get_text(" "))[:30] for r in rows[1:6] if r.find(["th", "td"])]})
        imgs = [i for i in body.find_all("img") if not is_boiler(i)]

        def big(i):
            src = (i.get("src") or i.get("data-src") or i.get("srcset") or "").lower()
            if not src or src.startswith("data:image/svg") or ".svg" in src or "icon" in src or "logo" in src or "flag" in src:
                return False
            try:
                return int(str(i.get("width") or "999").replace("px", "")) >= 100
            except ValueError:
                return True
        cimgs = [i for i in imgs if big(i)]
        alts = [tz.norm(i.get("alt")) for i in cimgs if tz.norm(i.get("alt"))]
        dup = Counter(alts).most_common(1)
        videos = len(body.find_all("video")) + len([f for f in body.find_all("iframe") if re.search(r"youtube|youtu\.be|vimeo|wistia", (f.get("src") or f.get("data-src") or ""), re.I)])

        faq_heads = [o["text"] for o in outline if pat["faq"].search(o["text"])]
        q_heads = [o["text"] for o in outline if o["text"].endswith("?")]
        q_other = [tz.norm(e.get_text(" ")) for e in body.find_all(["summary", "button", "dt", "h4", "h5", "strong"])
                   if tz.norm(e.get_text(" ")).endswith("?") and 15 < len(tz.norm(e.get_text(" "))) < 160]
        questions = [q for q in dict.fromkeys(faq_ld + q_heads + q_other) if not pat["question_ignore"].search(q)]
        faq = {"present": bool("FAQPage" in types or faq_heads or len(questions) >= 3), "schema_faqpage": "FAQPage" in types,
               "headings": faq_heads, "questions": questions[:40]}
        prices = pat["price"].findall(full_text)
        nums = sorted({int(re.sub(r"\D", "", re.split(r",\d{1,2}", p)[0]) or 0) for p in prices if p.lower().startswith("ab")} - {0})
        ctas = Counter()
        for e in body.find_all(["a", "button"]):
            t = tz.norm(e.get_text(" "))
            if 3 < len(t) < 45 and pat["cta"].search(t) and not is_boiler(e):
                ctas[t] += 1
        search_words = sorted({m.lower() for m in pat["search_form"].findall(full_text)})
        filt_words = sorted({m.lower() for m in pat["facets"].findall(full_text)})[:12]
        base = d.get("url") or url
        h = tz.host(base)
        links = []
        for a in body.find_all("a", href=True):
            href = urljoin(base, a["href"]).split("#")[0]
            if tz.host(href) == h:
                links.append({"href": href, "anchor": tz.norm(a.get_text(" "))[:80], "boiler": is_boiler(a)})
        head_txt = " | ".join(o["text"] for o in outline)
        rx = lambda r: re.compile(r"(?<!\w)" + re.escape(r) + r"(?!\w)", re.I)
        reg_head = [r for r in block_ents if rx(r).search(head_txt)]
        reg_links = sorted({r for r in block_ents for l in links if not l["boiler"] and rx(r).search(l["anchor"])})
        season_heads = [o["text"] for o in outline if season_re.search(o["text"])]
        months_text = {m: len(re.findall(r"(?<!\w)" + m + r"(?!\w)", main_text)) for m in months}
        month_table = any(sum(1 for m in months if m[:3].lower() in " ".join(t["header"] + t["first_col"]).lower()) >= 4 for t in tables)
        zones = {"title": title, "description": desc, "h1": " | ".join(h1), "headings": head_txt, "text": main_text}
        kws = {k: kw_presence(k, zones) for k in keywords}
        brand = h.split(".")[0].replace("-", " ")
        consent = bool(pat["consent"].search(title)) or (not h1 and tz.nosp(body_text) < cfg["cookie_wall_text_max"])
        status = d.get("status_code") or 0
        reason = (f"HTTP {status}" if status >= 400 else None) or ("cookie-стіна або сторінка без вмісту (title: «%s», H1 немає, тексту %d симв.)" % (title, tz.nosp(body_text)) if consent else None)
        res.update({
            "ok": reason is None, "fail_reason": reason,
            "title": title, "title_len": len(title), "description": desc, "description_len": len(desc), "h1": h1,
            "title_flags": {"main_keyword": tz.exact_count(ctx["main"], title) > 0, "year": sorted(set(re.findall(r"\b20[2-3]\d\b", title))),
                            "brand": any(b and b in title.lower() for b in (brand, brand.replace(" ", ""), brand.split(" ")[0]))},
            "description_symbols": dict(Counter(tz.symbols(desc))), "title_symbols": dict(Counter(tz.symbols(title))),
            "canonical": canon.get("href") if canon else None, "robots": robots.get("content") if robots else None,
            "outline": outline, "h2_count": sum(o["level"] == "h2" for o in outline), "h3_count": sum(o["level"] == "h3" for o in outline),
            "text_chars_nospace": tz.nosp(body_text), "text_words": len(re.findall(r"\w+", body_text)),
            "trafilatura_chars_nospace": tz.nosp(d.get("extracted_text") or ""),
            "lists": {"content": sum(l["kind"] == "content" for l in lists), "link_lists": sum(l["kind"] == "link-list" for l in lists), "samples": lists[:12]},
            "tables": {"count": len(tables), "items": tables[:8]},
            "images": {"total": len(imgs), "content": len(cimgs), "with_alt": len(alts), "alt_samples": alts[:10],
                       "duplicate_alt": {"alt": dup[0][0], "count": dup[0][1]} if dup and dup[0][1] > 1 else None},
            "videos": videos, "faq": faq,
            "prices": {"mentions": len(prices), "min_ab_price": nums[0] if nums else None, "samples": [tz.norm(p) for p in prices[:6]]},
            "reviews": {"aggregate_rating_schema": rating, "mentions": len(pat["review"].findall(full_text))},
            "filters": {"form_controls": len(body.find_all("select")) + len(body.find_all("input")), "search_form_words": search_words, "filter_words": filt_words,
                        "search_form": len(search_words) >= 2, "facets": any(w.startswith(("filter", "sortier")) for w in filt_words)},
            "cta": {"count": sum(ctas.values()), "top": ctas.most_common(10)},
            "regions": {"block": len(reg_head) >= 3 or len(reg_links) >= 4, "in_headings": reg_head, "in_link_anchors": reg_links,
                        "mentions_in_text": {r: n for r in ents if (n := len(rx(r).findall(main_text)))}},
            "seasons": {"block": bool(season_heads) or month_table, "headings": season_heads, "month_table": month_table,
                        "months_in_text": {k: v for k, v in months_text.items() if v}},
            "schema_types": types, "keywords_found": kws,
            "keywords_exact_any": sorted(k for k, v in kws.items() if v["text"] or v["title"] or v["h1"] or v["headings"] or v["description"]),
            "internal_links_content": len([l for l in links if not l["boiler"]]),
            "main_text": main_text, "body_text": body_text,
        })
        if own:
            res["internal_links"] = links
            res["ui_messages"] = ui
        return res
    return parse


def main():
    ap = tz.args_page(argparse.ArgumentParser())
    ap.add_argument("--refresh", action="store_true", help="рендерити заново, не брати з кешу")
    ap.add_argument("--offline", action="store_true", help="лише кеш competitors-raw/, без мережі")
    a = ap.parse_args()
    ctx = tz.load_ctx(a.workdir, a.page)
    if not os.path.exists(ctx["f"]["selection"]):
        tz.die("немає списку конкурентів. Спершу select_competitors.py.")
    sel = tz.rjson(ctx["f"]["selection"])
    if not sel.get("confirmed"):
        tz.die("список конкурентів не підтверджено користувачем. Покажіть його і запустіть select_competitors.py --confirm.")
    R, parse = Renderer(ctx, a.refresh, a.offline), make_parser(ctx)

    def analyse(url, own=False):
        attempts, res = [], None
        for mode in ("always", "auto"):
            d = R.get(url, mode, own=own and mode == "always")
            cur = parse(url, d, own)
            attempts.append({"mode": mode, "status": d.get("status_code"), "error": d.get("error"), "html_len": len(d.get("content") or "")})
            if res is None or cur["ok"] or not d.get("offline_miss"):
                res = cur          # a cache miss in --offline never hides the result of the first attempt
            if res["ok"] or own or d.get("offline_miss"):
                break
        res["attempts"] = attempts
        return res

    own = analyse(ctx["url"], own=True)
    if not own["ok"] and ctx["state"].startswith("існує"):
        tz.die(f"власна сторінка {ctx['url']} не відкрилася: {own.get('fail_reason')}. ТЗ без власної сторінки не збирається.")
    own["exists"] = own["ok"]
    print(f"OWN  {own.get('status')} text={own.get('text_chars_nospace')} {ctx['url']}" + ("" if own["ok"] else "  (сторінка нова — порівняння з нулем)"), flush=True)

    comps, replaced, reserves = [], [], [r["url"] for r in sel.get("reserves", [])]
    meta = {c["url"]: c for c in sel["selected"] + sel.get("reserves", [])}
    for c in sel["selected"]:
        u = c["url"]
        r = analyse(u)
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r.get('status')} text={r.get('text_chars_nospace')} {u} {'' if r['ok'] else r.get('fail_reason')}", flush=True)
        if not r["ok"]:
            rec = {"failed": u, "status": r.get("status"), "reason": r.get("fail_reason"), "tried": [], "replacement": None}
            while reserves:
                alt = reserves.pop(0)
                r2 = analyse(alt)
                print(f"     запасний {'OK  ' if r2['ok'] else 'FAIL'} {r2.get('status')} {alt} {'' if r2['ok'] else r2.get('fail_reason')}", flush=True)
                rec["tried"].append({"url": alt, "ok": r2["ok"], "status": r2.get("status"), "reason": r2.get("fail_reason")})
                if r2["ok"]:
                    r2["replaces"] = u
                    rec["replacement"] = alt
                    r = r2
                    break
            replaced.append(rec)
        m = meta.get(r["url"], {})
        r["serp_positions"], r["landing_type"], r["note"], r["serp_title"] = m.get("positions", {}), m.get("type"), m.get("note"), m.get("serp_title")
        comps.append(r)

    good = [c for c in comps if c["ok"]]
    if len(good) < 5:
        tz.die(f"відкрилося лише {len(good)} конкурентів — замало для медіан. Додайте запасні URL у {ctx['f']['selection']}.")
    n = len(good)
    med = lambda f: statistics.median(f(c) for c in good)
    cnt = lambda f: sum(1 for c in good if f(c))
    texts = sorted((c["text_chars_nospace"] for c in good), reverse=True)
    stop = set(re.findall(r"\w+", ctx["main"].lower())) | set(ctx["T"]["term_glue"])
    words = Counter()
    for c in good:
        brand = tz.host(c["url"]).split(".")[0]
        words.update({w for w in re.findall(r"[a-zäöüß]{4,}", c["title"].lower()) if w not in stop and w not in brand and brand not in w})
    sym = Counter()
    for c in good:
        sym.update({ctx["T"].get("symbol_names", {}).get(s, s) for s in c["description_symbols"]})
    summary = {
        "analysed_ok": n, "failed_without_replacement": [c["url"] for c in comps if not c["ok"]], "replaced": replaced,
        "text_median": int(med(lambda c: c["text_chars_nospace"])), "text_min": texts[-1], "text_max": texts[0], "text_top5": texts[:5],
        "h2_median": med(lambda c: c["h2_count"]), "h3_median": med(lambda c: c["h3_count"]),
        "lists_median": med(lambda c: c["lists"]["content"]), "tables_median": med(lambda c: c["tables"]["count"]),
        "images_median": int(med(lambda c: c["images"]["content"])),
        "with_faq": cnt(lambda c: c["faq"]["present"]), "with_faqpage": cnt(lambda c: c["faq"]["schema_faqpage"]),
        "with_tables": cnt(lambda c: c["tables"]["count"] > 0), "with_content_lists": cnt(lambda c: c["lists"]["content"] > 0),
        "with_region_block": cnt(lambda c: c["regions"]["block"]), "with_season_block": cnt(lambda c: c["seasons"]["block"]),
        "with_month_table": cnt(lambda c: c["seasons"]["month_table"]), "with_video": cnt(lambda c: c["videos"] > 0),
        "with_prices": cnt(lambda c: c["prices"]["mentions"] > 0), "with_reviews": cnt(lambda c: c["reviews"]["mentions"] > 0),
        "with_rating_schema": [tz.host(c["url"]) for c in good if c["reviews"]["aggregate_rating_schema"]],
        "title_main_keyword": cnt(lambda c: c["title_flags"]["main_keyword"]), "h1_main_keyword": cnt(lambda c: tz.exact_count(ctx["main"], " ".join(c["h1"])) > 0),
        "title_year": cnt(lambda c: c["title_flags"]["year"]), "title_brand": cnt(lambda c: c["title_flags"]["brand"]),
        "title_words": [{"word": w, "competitors": k} for w, k in words.most_common(12) if k >= 2],
        "description_symbols": dict(sym), "description_without_symbols": [tz.host(c["url"]) for c in good if not c["description_symbols"]],
        "main_keyword_exact_in_text": sorted(c["keywords_found"][ctx["main"]]["text"] for c in good),
    }
    tz.wjson(ctx["f"]["competitors"], {"page": ctx["url"], "slug": ctx["slug"], "main_keyword": ctx["main"],
                                       "adjacent": [k["keyword"] for k in sel["forming_keywords"] if k["role"] != "головний"],
                                       "forming_keywords": sel["forming_keywords"],
                                       "hub_keywords": [{"keyword": k["keyword"], "translation": k["translation"], "volume": k["volume"]} for k in ctx["keys"]],
                                       "summary": summary, "competitors": comps, "own": own})
    print("saved", ctx["f"]["competitors"])
    print(json.dumps({k: v for k, v in summary.items() if k != "replaced"}, ensure_ascii=False, indent=1))
    for r in replaced:
        print(f"ЗАМІНА: {r['failed']} — {r['reason']} → {r['replacement'] or 'заміни немає'}; пробували: " + ", ".join(f"{t['url']} ({'ок' if t['ok'] else t['reason']})" for t in r["tried"]))


if __name__ == "__main__":
    main()
