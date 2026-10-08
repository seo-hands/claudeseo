#!/usr/bin/env python3
"""semantics-travel / collect: keyword collection for ONE page (mode full, step 1; paid).

Three separate runs, each with its own confirmation (nothing is requested without --yes):
  0) python collect.py --propose-seeds [--topics de=Türkei ru=Турция]      NO API: seed list from the profile -> show to the user, wait for confirmation
  1) python collect.py --url https://site/page --seeds "seed 1" "seed 2" [--competitors 3] [--yes]
        first collection from the CONFIRMED seeds (estimate first; --yes only after the user agreed)
  2) python collect.py --snowball [--yes]       second expansion: 5-10 highest-volume NEW core keywords (no region, no other product) -> suggestions+related
        (separate estimate, separate confirmation)
  python collect.py --seeds "seed" --replay collect-raw     re-parse saved raw responses (no API, no --yes)

Steps of run 1 (known prices only): Labs ranked_keywords of the page; Labs keyword_suggestions + related_keywords per seed;
SERP (live/regular) of the first seed -> competitor pages -> Labs ranked_keywords of N of them; Labs bulk_keyword_difficulty.

Topic boundaries (scope.py + profile "scope"): every keyword is labelled
  core (page topic + modifiers) -> clustered and distributed; limited to max_keywords (default 100) by volume;
        core keywords of volume 10-50 that did not fit the limit -> keywords.json["longtail"] -> sheet «Довгий хвіст» (for the copywriter, no clustering)
  adjacent (another region/district or another product: hot tours, hotels, flights, excursions...) -> keywords.json["adjacent"] -> sheet «Напрямки розширення»
        (NOT discarded; the limit does not apply)
  junk (weather, visa, news, maps, competitor brands, irrelevant, stale years, volume < 10, duplicates) -> keywords.json["filtered"] with the reason -> «Відфільтровані»
Raw responses -> collect-raw/, the unfiltered candidate pool -> collect-pool.json (needed by --snowball and re-filtering).
"""
import argparse, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C
import scope as SC

LABS = "dataforseo_labs/google/"
LONGTAIL_MAX_VOLUME = 50
SNOWBALL_N = (5, 10)
SNOWBALL_DEFAULT = 5


def seed_slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "seed"


def items_of(resp, kind):
    out = []
    for res in (resp["tasks"][0].get("result") or []):
        for it in (res.get("items") or []):
            kd = it["keyword_data"] if kind in ("ranked", "related") else it
            ki = kd.get("keyword_info") or {}
            rec = {"keyword": kd["keyword"], "volume": ki.get("search_volume") or 0, "cpc": ki.get("cpc"),
                   "intent": (kd.get("search_intent_info") or {}).get("main_intent"), "kd": (kd.get("keyword_properties") or {}).get("keyword_difficulty")}
            if kind == "ranked":
                rec["own_position"] = (it.get("ranked_serp_element") or {}).get("serp_item", {}).get("rank_group")
            out.append(rec)
    return out


def vol_filter(path):
    return [[path + "search_volume", ">=", 10]]


# ---------------------------------------------------------------- 0) seed proposal (no API)
def propose_seeds(S, a):
    topics = dict(t.split("=", 1) for t in (a.topics or []))
    langs = [S.language] + [x for x in re.split(r"[|,; ]+", S.get("semantic_languages", "")) if x and x != S.language]
    out = {}
    print("ПРОПОЗИЦІЯ SEED (без запитів до API; відредагуйте й підтвердьте список):\n")
    for lang in langs:
        try:
            P = C.load_profile(S if lang == S.language else C.Settings(dict(S, language=lang, profile=lang)), a.workdir)
        except C.ProfileMissing as e:
            print(f"[{lang}] профілю немає - {e}\n")
            continue
        t = topics.get(lang) or (S.country if lang == S.language else "")
        if not t:
            print(f"[{lang}] вкажіть назву теми цією мовою: --topics {lang}=<назва>\n")
            continue
        tpl = P.get("seed_templates", {})
        print(f"== мова {lang}, тема «{t}» ==")
        out[lang] = {}
        for grp, title in (("main", "головний запит"), ("product_synonyms", "синоніми продукту"), ("word_order", "варіанти порядку слів"),
                           ("adjacent_optional", "суміжне (необов'язково, лише якщо потрібна й ця семантика)")):
            lst = [x.replace("{t}", t.lower()) for x in tpl.get(grp, [])]
            out[lang][grp] = lst
            print(f"{title}:")
            for x in lst:
                print("   -", x)
        print()
    json.dump(out, open(os.path.join(a.workdir, "seed-proposal.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Збережено seed-proposal.json. Після підтвердження користувачем: collect.py --url ... --seeds <підтверджений список> (спершу без --yes: оцінка вартості).")


# ---------------------------------------------------------------- filtering / labelling (also used by snowball and replay)
def process(cands, S, R, SCP, competitor_domains, seeds, max_keywords):
    year = datetime.date.today().year
    site_dom = C.reg_domain(re.sub(r"^https?://", "", S.site))
    brand_tokens = set()
    for d in competitor_domains + [site_dom]:
        label = d.split(".")[0]
        if len(label) >= 4:
            brand_tokens.add(label)
            brand_tokens.update(x for x in label.split("-") if len(x) >= 4)
    stop = [r"(?<!\w)(?:" + "|".join(getattr(R, "STOP_BRANDS", [])) + r")(?!\w)"] if getattr(R, "STOP_BRANDS", None) else []   # whole-word stop brands of the market profile
    all_brands = S.brands + stop
    brand_rx = re.compile("|".join(all_brands + [re.escape(t) for t in sorted(brand_tokens)]), re.I) if (all_brands or brand_tokens) else None
    prod_rx = re.compile("|".join(S.exclude_products), re.I) if S.exclude_products else None
    topic = {S.country.lower()} | set(S.hub_slugs.split("|")) | set(S.regions) | {w for s in seeds for w in re.findall(r"\w{4,}", s.lower())}
    core, adjacent, filtered, seen = {}, {}, [], {}
    for c in sorted(cands, key=lambda x: -x["volume"]):
        k, kl = c["keyword"], c["keyword"].lower()
        reason, lab, theme = None, SC.CORE, ""
        if c["volume"] < 10:
            reason = "частотність < 10"
        elif brand_rx and brand_rx.search(kl):
            reason = "бренд конкурента / навігаційний"
        elif prod_rx and prod_rx.search(kl):
            reason = "запит про інший продукт, який сайт не продає"
        elif not any(t in kl for t in topic):
            reason = "нерелевантний (немає теми сторінки)"
        else:
            ys = [int(y) for y in re.findall(r"\b(20\d\d)\b", kl)]
            if ys and max(ys) < year:
                reason = f"застарілий рік ({max(ys)})"
        if not reason:
            lab, theme, why = SCP.label(k)
            if lab == SC.JUNK:
                reason = why
        if not reason:
            nk = C.norm_keyword(k, R)
            if nk in seen:
                reason = f"дублікат (той самий запит: «{seen[nk]}»)"
            else:
                seen[nk] = k
        if reason:
            filtered.append({"keyword": k, "volume": c["volume"], "reason": reason})
        elif lab == SC.ADJ:
            adjacent[k] = dict(c, theme=theme, label="суміжне")
        else:
            core[k] = dict(c, label="ядро")
    ranked = sorted(core.values(), key=lambda x: -x["volume"])
    keep, over = ranked[:max_keywords], ranked[max_keywords:]
    longtail = [c for c in over if c["volume"] <= LONGTAIL_MAX_VOLUME]
    for c in over:
        if c["volume"] > LONGTAIL_MAX_VOLUME:
            filtered.append({"keyword": c["keyword"], "volume": c["volume"], "reason": f"ядро понад ліміт {max_keywords} ключів (нижча частотність)"})
    return keep, longtail, sorted(adjacent.values(), key=lambda x: -x["volume"]), filtered


def snowball_seeds(pool_cands, SCP, used, n_max=SNOWBALL_N[1]):
    """Highest-volume NEW keywords of the core without a region/district name and without another product."""
    out, seen = [], {u.lower() for u in used}
    for c in sorted(pool_cands, key=lambda x: -x["volume"]):
        k = c["keyword"]
        if k.lower() in seen or c["volume"] < 10:
            continue
        lab, _, _ = SCP.label(k)
        if lab != SC.CORE or SCP.region_of(k.lower()) or SCP.product_of(k.lower()):
            continue
        seen.add(k.lower())
        out.append(k)
        if len(out) >= n_max:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--url")
    ap.add_argument("--seeds", nargs="+")
    ap.add_argument("--propose-seeds", action="store_true", help="step 0: propose the seed list (no API)")
    ap.add_argument("--topics", nargs="+", help="lang=name of the topic in each semantic language, e.g. de=Türkei ru=Турция")
    ap.add_argument("--snowball", action="store_true", help="step 2: second expansion from the 5-10 highest-volume new core keywords (separate estimate)")
    ap.add_argument("--snowball-n", type=int, default=SNOWBALL_DEFAULT, help="5..10 seeds (default 5)")
    ap.add_argument("--with-related", action="store_true", help="snowball: also related_keywords per seed (default: only keyword_suggestions)")
    ap.add_argument("--competitors", type=int, default=3)
    ap.add_argument("--merge", action="store_true", help="add new keywords to an existing keywords.json instead of replacing it")
    ap.add_argument("--replay")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    try:
        S = C.load_settings(a.workdir, a.claude_md)
    except C.ConfigMissing as e:
        sys.exit(C.config_help(e))
    if a.propose_seeds:
        return propose_seeds(S, a)
    if not a.snowball and not a.seeds:
        sys.exit("Немає підтвердженого списку seed. Спершу: collect.py --propose-seeds (без API), покажіть список користувачу, після підтвердження передайте --seeds.")
    R, _ = C.load_rules(S, a.workdir)
    SCP = SC.Scope(C.load_profile(S, a.workdir), R, S)
    raw_dir = os.path.join(a.workdir, "collect-raw")
    pool_fn = os.path.join(a.workdir, "collect-pool.json")
    kw_fn = os.path.join(a.workdir, "keywords.json")
    base = {"location_code": S.location_code, "language_code": S.language}
    pool = json.load(open(pool_fn, encoding="utf-8")) if os.path.exists(pool_fn) else {"cands": [], "competitor_domains": [], "seeds": [], "snowball_seeds": []}

    # ---------------- estimate ----------------
    if a.snowball:
        if not pool["cands"]:
            sys.exit("Немає collect-pool.json: спершу виконайте перший збір (--seeds).")
        used = pool["seeds"] + pool["snowball_seeds"]
        snow = snowball_seeds(pool["cands"], SCP, used, max(SNOWBALL_N[0], min(SNOWBALL_N[1], a.snowball_n)))
        if len(snow) < SNOWBALL_N[0]:
            print(f"Увага: знайдено лише {len(snow)} нових ключів ядра без району/іншого продукту (потрібно {SNOWBALL_N[0]}-{SNOWBALL_N[1]}).")
        if not snow:
            return
        print("SNOWBALL seed (найчастотніші нові ключі ядра, без району й без іншого продукту):")
        vol = {c["keyword"]: c["volume"] for c in pool["cands"]}
        for s_ in snow:
            print(f"   - {s_} ({vol.get(s_, 0)})")
        seeds_run = snow
        rows = [("Labs keyword_suggestions (snowball seed)", len(snow), C.PRICES["labs_keyword_suggestions"])]
        if a.with_related:
            rows.append(("Labs related_keywords (snowball seed)", len(snow), C.PRICES["labs_related_keywords"]))
        rows.append(("Labs bulk_keyword_difficulty (нові ключі)", 1, C.PRICES["labs_bulk_keyword_difficulty"]))
    else:
        seeds_run = a.seeds
        rows = []
        if a.url:
            rows.append(("Labs ranked_keywords сторінки", 1, C.PRICES["labs_ranked_keywords"]))
        rows.append(("Labs keyword_suggestions (seed)", len(a.seeds), C.PRICES["labs_keyword_suggestions"]))
        rows.append(("Labs related_keywords (seed)", len(a.seeds), C.PRICES["labs_related_keywords"]))
        rows.append(("SERP першого seed (пошук конкурентів)", 1, C.PRICES["serp_live_regular"]))
        rows.append(("Labs ranked_keywords сторінок конкурентів", a.competitors, C.PRICES["labs_ranked_keywords"]))
        rows.append(("Labs bulk_keyword_difficulty (до 1000 ключів)", 1, C.PRICES["labs_bulk_keyword_difficulty"]))
    est = C.print_estimate(rows)
    if not a.replay and not a.yes:
        print("Запити НЕ виконано. Покажіть оцінку користувачу, дочекайтесь підтвердження і запустіть з --yes.")
        return

    guard = C.CostGuard(est)
    auth = None if a.replay else C.load_auth()
    os.makedirs(raw_dir, exist_ok=True)
    cands, competitor_domains = [], []
    prefix = "snow-" if a.snowball else ""

    def call(name, path, body, kind, src):
        fn = os.path.join(a.replay or raw_dir, name + ".json")
        if a.replay:
            if not os.path.exists(fn):
                return []
            resp = json.load(open(fn, encoding="utf-8"))
        else:
            resp = C.api(auth, path, [body])
            json.dump(resp, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            guard.add(resp.get("cost"))
        got = items_of(resp, kind)
        for g in got:
            g["source"] = src
        print(f"{name}: {len(got)} ключів")
        return got

    if not a.snowball and a.url:
        cands += call("ranked-page", LABS + "ranked_keywords/live", dict(base, target=a.url, limit=100, filters=vol_filter("keyword_data.keyword_info."),
                                                                      order_by=["keyword_data.keyword_info.search_volume,desc"]), "ranked", "ranked")
    for seed in seeds_run:
        cands += call(prefix + "suggestions-" + seed_slug(seed), LABS + "keyword_suggestions/live",
                      dict(base, keyword=seed, limit=100, filters=vol_filter("keyword_info."), order_by=["keyword_info.search_volume,desc"]), "suggestions", f"{'snowball' if a.snowball else 'suggestions'}:{seed}")
        if a.snowball and not a.with_related:
            continue
        cands += call(prefix + "related-" + seed_slug(seed), LABS + "related_keywords/live",
                      dict(base, keyword=seed, depth=1, limit=60, filters=vol_filter("keyword_data.keyword_info."), order_by=["keyword_data.keyword_info.search_volume,desc"]),
                      "related", f"{'snowball' if a.snowball else 'related'}:{seed}")

    if not a.snowball:
        # competitors from the SERP of the first seed
        sfn = os.path.join(a.replay or raw_dir, "serp-seed.json")
        if a.replay:
            sresp = json.load(open(sfn, encoding="utf-8")) if os.path.exists(sfn) else None
        else:
            sresp = C.api(auth, "serp/google/organic/live/regular", [{"keyword": a.seeds[0], "location_code": S.location_code, "language_code": S.language,
                                                                     "se_domain": S.se_domain, "device": "desktop", "depth": 10}])
            json.dump(sresp, open(sfn, "w", encoding="utf-8"), ensure_ascii=False)
            guard.add(sresp.get("cost"))
        comp_urls = []
        if sresp:
            site_dom = C.reg_domain(re.sub(r"^https?://", "", S.site))
            for it in (sresp["tasks"][0]["result"][0]["items"]):
                if it["type"] != "organic":
                    continue
                dom = C.reg_domain(it["domain"])
                competitor_domains.append(dom)
                typ, _ = R.classify_url(it["url"], it.get("title") or "")
                if typ in ("info", "other", "hotel") or dom == site_dom or any(C.reg_domain(u.split("/")[2]) == dom for u in comp_urls):
                    continue
                comp_urls.append(it["url"])
        for i, u in enumerate(comp_urls[: a.competitors]):
            cands += call(f"competitor-{i + 1}", LABS + "ranked_keywords/live", dict(base, target=u, limit=50, filters=vol_filter("keyword_data.keyword_info."),
                                                                                    order_by=["keyword_data.keyword_info.search_volume,desc"]), "ranked", f"competitor:{C.reg_domain(u.split('/')[2])}")
        pool = {"cands": [], "competitor_domains": competitor_domains, "seeds": list(a.seeds), "snowball_seeds": []}
    else:
        pool["snowball_seeds"] = pool["snowball_seeds"] + list(seeds_run)

    # pool = every candidate ever collected (unfiltered); the filter always runs over the whole pool, so snowball cannot lose anything
    have = {c["keyword"]: c for c in pool["cands"]}
    for c in cands:
        if c["keyword"] not in have or c["volume"] > have[c["keyword"]]["volume"]:
            have[c["keyword"]] = c
    pool["cands"] = list(have.values())
    json.dump(pool, open(pool_fn, "w", encoding="utf-8"), ensure_ascii=False)

    all_seeds = pool["seeds"] + pool["snowball_seeds"]
    keep, longtail, adjacent, filtered = process(pool["cands"], S, R, SCP, pool["competitor_domains"], all_seeds, S.max_keywords)

    # KD for the kept core list (snowball: only for keywords without KD)
    need = [c for c in keep if c.get("kd") is None]
    if need and not a.replay:
        kdresp = C.api(auth, LABS + "bulk_keyword_difficulty/live", [dict(base, keywords=[c["keyword"] for c in need][:1000])])
        json.dump(kdresp, open(os.path.join(raw_dir, prefix + "kd.json"), "w", encoding="utf-8"), ensure_ascii=False)
        guard.add(kdresp.get("cost"))
        kd = {i["keyword"]: i.get("keyword_difficulty") for res in (kdresp["tasks"][0].get("result") or []) for i in (res.get("items") or [])}
        for c in need:
            c["kd"] = kd.get(c["keyword"], c.get("kd"))
    elif a.replay and os.path.exists(os.path.join(a.replay, "kd.json")):
        kdresp = json.load(open(os.path.join(a.replay, "kd.json"), encoding="utf-8"))
        kd = {i["keyword"]: i.get("keyword_difficulty") for res in (kdresp["tasks"][0].get("result") or []) for i in (res.get("items") or [])}
        for c in keep:
            c["kd"] = kd.get(c["keyword"], c.get("kd"))

    meta = {"url": a.url, "seeds": pool["seeds"], "snowball_seeds": pool["snowball_seeds"], "collected": str(datetime.date.today()),
            "cost_usd": round(guard.spent, 4), "max_keywords": S.max_keywords}
    out = {"keywords": keep, "longtail": longtail, "adjacent": adjacent, "filtered": filtered, "meta": meta}
    if os.path.exists(kw_fn):
        old = json.load(open(kw_fn, encoding="utf-8"))
        # keep what was added by the other modes (region extensions) and the translations/decisions already made
        ext = [k for k in old.get("keywords", []) if str(k.get("source", "")).startswith("region:")]
        tr = {k["keyword"]: k for k in old.get("keywords", []) + old.get("longtail", []) if k.get("translation_uk")}
        for k in keep + longtail:
            if k["keyword"] in tr:
                k["translation_uk"] = tr[k["keyword"]]["translation_uk"]
                if tr[k["keyword"]].get("translation_note_uk"):
                    k["translation_note_uk"] = tr[k["keyword"]]["translation_note_uk"]
        out["keywords"] = keep + [k for k in ext if k["keyword"] not in {x["keyword"] for x in keep}]
        meta["cost_usd"] = round(old.get("meta", {}).get("cost_usd", 0) + guard.spent, 4)
    json.dump(out, open(kw_fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"ядро {len(keep)} (довгий хвіст {len(longtail)}), суміжне {len(adjacent)} (обсяг {sum(x['volume'] for x in adjacent)}), "
          f"відфільтровано {len(filtered)}; витрати {guard}")
    if not a.snowball:
        print("Далі (за бажанням): collect.py --snowball (окрема оцінка й підтвердження); потім translations.py, fetch_serp.py (платно), analyze.py.")
    else:
        print("Далі: translations.py, fetch_serp.py для нових ключів ядра (платно, з підтвердженням), analyze.py.")


if __name__ == "__main__":
    main()
