#!/usr/bin/env python3
"""semantics-travel / extend_region: demand check for a region/district (mode extend-region, paid).

python extend_region.py --region <name> [--seeds "<name> <word>" "<name> <country>"] [--serp 3] [--serp-extra "kw" ...] [--workdir .] [--yes]
python extend_region.py --region <name> --replay region-<slug>-raw      re-parse saved raw responses (no API calls)

Why: collecting only from the main word misses regional demand (a district name + country query can be missing from the country list).
Steps: Labs keyword_suggestions + related_keywords per seed, then SERP (live/regular, location_code + se_domain) for the N biggest GENERAL
keywords (+ any --serp-extra) classified with the preset's landing-page rules.  Estimate first; without --yes nothing is requested.
Result: region-<slug>-demand.json with an automatic group per keyword (general / hotels_list / hotel_name / info) for REVIEW.
Next: Claude reviews the groups, translates, writes a classification file, then add_region.py puts the keywords into keywords.json.
Defaults for seeds: "<region> <seed word>" and "<region> <country>" (seed word from the preset).
"""
import argparse, collections, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C

LABS = "dataforseo_labs/google/"


def sslug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def items(resp, related):
    out = []
    for res in (resp["tasks"][0].get("result") or []):
        for it in (res.get("items") or []):
            kd = it["keyword_data"] if related else it
            ki = kd.get("keyword_info") or {}
            out.append({"keyword": kd["keyword"], "volume": ki.get("search_volume") or 0, "cpc": ki.get("cpc"),
                        "intent": (kd.get("search_intent_info") or {}).get("main_intent"), "kd": (kd.get("keyword_properties") or {}).get("keyword_difficulty")})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--region", required=True)
    ap.add_argument("--seeds", nargs="+")
    ap.add_argument("--serp", type=int, default=3)
    ap.add_argument("--serp-extra", nargs="*", default=[])
    ap.add_argument("--replay")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    try:
        S = C.load_settings(a.workdir, a.claude_md)
    except C.ConfigMissing as e:
        sys.exit(C.config_help(e))
    R, _ = C.load_rules(S, a.workdir)
    slug = sslug(a.region)
    seeds = a.seeds or [f"{a.region} {getattr(R, 'REGION_SEED_WORD', 'urlaub')}", f"{a.region} {S.country.lower()}"]
    raw = os.path.join(a.workdir, f"region-{slug}-raw")
    base = {"location_code": S.location_code, "language_code": S.language, "limit": 100}
    n_serp = a.serp + len(a.serp_extra)
    est = C.print_estimate([("Labs keyword_suggestions (seed)", len(seeds), C.PRICES["labs_keyword_suggestions"]),
                            ("Labs related_keywords (seed)", len(seeds), C.PRICES["labs_related_keywords"]),
                            ("SERP live/regular (найбільші загальні ключі)", n_serp, C.PRICES["serp_live_regular"])])
    if not a.replay and not a.yes:
        print("Запити НЕ виконано. Покажіть оцінку користувачу, дочекайтесь підтвердження і запустіть з --yes.")
        return
    guard = C.CostGuard(est)
    auth = None if a.replay else C.load_auth()
    os.makedirs(raw, exist_ok=True)
    cands = []
    for seed in seeds:
        for kind, path, body, rel in (("suggestions", LABS + "keyword_suggestions/live",
                                       dict(base, keyword=seed, filters=[["keyword_info.search_volume", ">=", 10]], order_by=["keyword_info.search_volume,desc"]), False),
                                      ("related", LABS + "related_keywords/live",
                                       dict(base, keyword=seed, depth=1, limit=60, filters=[["keyword_data.keyword_info.search_volume", ">=", 10]],
                                            order_by=["keyword_data.keyword_info.search_volume,desc"]), True)):
            fn = os.path.join(a.replay or raw, f"{kind}-{sslug(seed)}.json")
            if a.replay or os.path.exists(fn):
                if not os.path.exists(fn):
                    continue
                resp = json.load(open(fn, encoding="utf-8"))            # cached: not paid twice
            else:
                resp = C.api(auth, path, [body])
                json.dump(resp, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
                guard.add(resp.get("cost"))
            got = items(resp, rel)
            for g in got:
                g["source"] = f"{kind}:{seed}"
            print(f"{kind} '{seed}': {len(got)} ключів")
            cands += got
    rx = re.compile(r"(?<![a-z])" + re.escape(a.region.lower()) + r"(?![a-z])")
    best = {}
    for c in cands:
        if not rx.search(c["keyword"].lower()):
            continue
        nk = C.norm_keyword(c["keyword"], R)
        if nk not in best or c["volume"] > best[nk]["volume"]:
            best[nk] = dict(c, variants=best.get(nk, {}).get("variants", []))
        if c["keyword"] != best[nk]["keyword"]:
            best[nk]["variants"].append(c["keyword"])
    rows = sorted(best.values(), key=lambda r: -r["volume"])
    generic = getattr(R, "GENERIC_TOKENS", set()) | {a.region.lower(), S.country.lower()}
    info_tok, list_tok, noise = getattr(R, "INFO_TOKENS", set()), getattr(R, "HOTEL_LIST_TOKENS", set()), getattr(R, "BRAND_NOISE", set())
    for r in rows:
        toks = re.findall(r"\w+", r["keyword"].lower())
        extra = [t for t in toks if t not in generic and not t.isdigit()]
        r["auto_group"] = "info" if any(t in info_tok for t in toks) else "hotel_name" if extra else "hotels_list" if any(t in list_tok for t in toks) else "general"
        r["entity"] = " ".join(sorted(t for t in extra if t not in noise))
    seen, ded = {}, []                     # the same hotel written in different ways -> one row
    for r in rows:
        if r["auto_group"] == "hotel_name" and r["entity"]:
            if r["entity"] in seen:
                seen[r["entity"]]["variants"].append(r["keyword"])
                continue
            seen[r["entity"]] = r
        ded.append(r)
    rows = ded
    # SERP for the biggest general keywords
    serp_out = {}
    targets = [r["keyword"] for r in rows if r["auto_group"] == "general"][: a.serp] + a.serp_extra
    sdir = os.path.join(a.replay or raw, "serp")
    os.makedirs(sdir, exist_ok=True)
    for kw in targets:
        fn = os.path.join(sdir, C.slug_file(kw) + ".json")
        if os.path.exists(fn):
            d = json.load(open(fn, encoding="utf-8"))
        elif a.replay:
            continue
        else:
            params = {"keyword": kw, "location_code": S.location_code, "language_code": S.language, "se_domain": S.se_domain, "device": "desktop", "depth": 10}
            resp = C.api(auth, "serp/google/organic/live/regular", [params])
            d = {"keyword": kw, "request": params, "response": resp}
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            guard.add(resp.get("cost"))
        res = d["response"]["tasks"][0]["result"][0]
        res_rows = []
        for it in res["items"]:
            if it["type"] == "organic":
                typ, reg = R.classify_url(it["url"], it.get("title") or "")
                res_rows.append({"position": it["rank_group"], "url": it["url"], "domain": it["domain"], "title": it.get("title") or "", "type": R.type_label(typ, reg), "region": reg})
        serp_out[kw] = {"check_url": res.get("check_url"), "datetime": res.get("datetime"), "results": res_rows}
    out = {"region": a.region, "slug": slug, "seeds": seeds, "cost_usd": round(guard.spent, 4), "keywords": rows, "serp": serp_out}
    json.dump(out, open(os.path.join(a.workdir, f"region-{slug}-demand.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = collections.Counter()
    for r in rows:
        tot[r["auto_group"]] += r["volume"]
    print(f"\nключів про «{a.region}»: {len(rows)}; обсяг за групами: {dict(tot)}; витрати {guard}")
    for r in rows[:20]:
        print(f"{r['volume']:>6} {r['auto_group']:<12} {r['keyword']}")
    for kw, v in serp_out.items():
        c = collections.Counter(x["type"] for x in v["results"])
        print(f"\nSERP «{kw}»: {dict(c)}  check_url: {v['check_url']}")
    print("\nДалі: переглянути групи, перекласти, скласти classification.json і запустити add_region.py.")


if __name__ == "__main__":
    main()
