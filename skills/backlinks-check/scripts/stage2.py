#!/usr/bin/env python3
"""Stage 2 (candidates): 12-month donor history (trend by dofollow donors), top-100 donors by rank; for market-TLD
domains also 12-month traffic history and top-100 keywords; a point check of a free-hosting spam zone; page checks
(fetch_pages); then final flags, verdict_auto and the automatic priority.  Writes stage2.json and pages.json."""
import collections, datetime, re, sys
import bl_common as bl
import rules
import fetch_pages

S = "2"


def months_back(today, n):
    d = datetime.date.fromisoformat(today)
    y, m = d.year, d.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}-01"


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--candidates", default="", help="кандидати через кому; без параметра — candidates зі stage1.json (або candidates_auto)")
    a = ap.parse_args()
    if not a.run:
        sys.exit("потрібен --run")
    run = bl.Run(a)
    s1 = run.load("stage1.json")
    if not s1:
        sys.exit("Спершу stage1.py")
    market, inp, D = run.market, run.input, s1["domains"]
    cands = [bl.norm_domain(x) for x in a.candidates.split(",") if x.strip()] or s1.get("candidates") or s1["candidates_auto"]
    unknown = [c for c in cands if c not in D]
    if unknown:
        sys.exit(f"Кандидатів немає у списку доменів: {', '.join(unknown)}")
    s1["candidates"] = cands
    run.save("stage1.json", s1)
    theme = re.compile(bl.CFG["themes"][inp["theme"]], re.I)
    notes = run.load("site-notes.json", {})

    P, _ = bl.plan_stage2(run, cands)
    need = [p for p in P if not p["cached"] and not p["domain"].startswith("(")]
    if need:
        bl.print_plan(P, run.budget, run.spent(), show_missing=run.offline)
        if run.offline:
            sys.exit("Офлайн: у кеші бракує відповідей етапу 2 (список вище) — платних запитів не виконано.")
        if not run.yes:
            sys.exit("Це кошторис. Для платних запитів додай --yes.")
    bal0 = run.balance("before_stage2") if need else None
    run.hits = {}

    C = {}
    for d in cands:
        m, tld = D[d], bl.is_market_tld(d, market)
        c = C[d] = {"scope": "повний" if tld else "скорочений (без historical і ranked_keywords)"}
        r = run.call(S, d, bl.EP_TS, "backlinks/timeseries_summary/live", {"target": d, "date_from": months_back(run.today, 12), "date_to": run.today, "group_range": "month"},
                     "backlinks_timeseries_summary")
        ts = [{"m": i["date"][:7], "rd": i.get("referring_domains") or 0, "dofollow": (i.get("referring_domains") or 0) - (i.get("referring_domains_nofollow") or 0),
               "main": i.get("referring_main_domains"), "backlinks": i.get("backlinks"), "rank": i.get("rank")} for i in bl.result(r).get("items") or []]
        c["ts"] = ts
        if ts:
            c["dofollow_first"], c["dofollow_last"] = ts[0]["dofollow"], ts[-1]["dofollow"]
            c["dofollow_change"] = bl.pct(ts[0]["dofollow"], ts[-1]["dofollow"])
            if len(ts) >= 4 and ts[-4]["dofollow"] and ts[-1]["dofollow"] / ts[-4]["dofollow"] >= rules.SPIKE_RATIO and ts[-1]["dofollow"] - ts[-4]["dofollow"] >= 100:
                c["spike"] = [ts[-4]["dofollow"], ts[-1]["dofollow"]]
        r = run.call(S, d, bl.EP_REF, "backlinks/referring_domains/live", {"target": d, "limit": 100, "order_by": ["rank,desc"]}, "backlinks_referring_domains", 100)
        res = bl.result(r)
        ref = [{"domain": i["domain"], "rank": i.get("rank") or 0, "backlinks": i.get("backlinks"), "first_seen": (i.get("first_seen") or "")[:10]} for i in res.get("items") or []]
        c["ref_total"], c["ref_top10"] = res.get("total_count"), ref[:10]
        c["buckets"] = {"400+": sum(1 for x in ref if x["rank"] >= 400), "300-399": sum(1 for x in ref if 300 <= x["rank"] < 400), "200-299": sum(1 for x in ref if 200 <= x["rank"] < 300),
                        "100-199": sum(1 for x in ref if 100 <= x["rank"] < 200), "<100": sum(1 for x in ref if x["rank"] < 100)}
        if tld:
            lg = m.get("dominant_lang") or bl.market_langs(run)[0]
            c["lang"] = lg
            r = run.call(S, d, bl.ep_hist(run, lg), "dataforseo_labs/google/historical_rank_overview/live",
                         {"target": d, "location_code": market["location_code"], "language_code": lg, "date_from": months_back(run.today, 13), "ignore_synonyms": True}, "labs_historical_rank_overview")
            h = []
            for it in bl.result(r).get("items") or []:
                o = it["metrics"]["organic"]
                h.append({"m": f"{it['year']}-{it['month']:02d}", "etv": round(o.get("etv") or 0), "top10": (o.get("pos_1") or 0) + (o.get("pos_2_3") or 0) + (o.get("pos_4_10") or 0)})
            c["hist"] = sorted(h, key=lambda x: x["m"])
            if c["hist"]:
                c["traffic_change"] = bl.pct(c["hist"][0]["etv"], c["hist"][-1]["etv"])
            r = run.call(S, d, bl.ep_ranked(run, lg), "dataforseo_labs/google/ranked_keywords/live",
                         {"target": d, "location_code": market["location_code"], "language_code": lg, "limit": 100, "item_types": ["organic"],
                          "order_by": ["ranked_serp_element.serp_item.etv,desc"]}, "labs_ranked_keywords", 100)
            res = bl.result(r)
            kws, pages = [], collections.defaultdict(float)
            for it in res.get("items") or []:
                si, kd = it["ranked_serp_element"]["serp_item"], it["keyword_data"]
                kws.append({"keyword": kd["keyword"], "volume": kd["keyword_info"].get("search_volume"), "pos": si.get("rank_group"), "etv": round(si.get("etv") or 0, 1), "url": si.get("url")})
                pages[si.get("url")] += si.get("etv") or 0
            c["kws"], c["kw_total"] = kws, res.get("total_count")
            c["top_pages"] = [{"url": u, "etv": round(e)} for u, e in sorted(pages.items(), key=lambda x: -x[1])[:5]]
            tot = sum(k["etv"] for k in kws)
            th = [k for k in kws if theme.search(k["keyword"])]
            c["theme_kws"], c["theme_etv"], c["kw_etv"] = len(th), round(sum(k["etv"] for k in th)), round(tot)
            cas = [k for k in kws if bl.CASINO_BRAND.search(k["keyword"]) and not bl.NEWS.search(k["keyword"])]
            if cas and tot:
                best = max(cas, key=lambda k: k["etv"])
                share = sum(k["etv"] for k in cas if k["url"] == best["url"]) / tot
                if share >= rules.CASINO_KW_SHARE:
                    c["casino_kw"] = {"keyword": best["keyword"], "url": best["url"], "share": round(share, 3), "pos": best["pos"]}
        if m.get("spam_zone"):
            z = m["spam_zone"]
            r = run.call(S, d, bl.ep_zone(z), "backlinks/referring_domains/live", {"target": d, "limit": 30, "order_by": ["backlinks,desc"], "filters": ["domain", "like", "%" + z]},
                         "backlinks_referring_domains", 30)
            res = bl.result(r)
            items = [{"domain": i["domain"], "rank": i.get("rank") or 0, "backlinks": i.get("backlinks"), "first_seen": (i.get("first_seen") or "")[:10]} for i in res.get("items") or []]
            years = collections.Counter(i["first_seen"][:4] for i in items)
            c["zone"] = {"zone": z, "links": m["spam_zone_links"], "domains": res.get("total_count"), "items": items[:12], "rank0": sum(1 for i in items if not i["rank"]),
                         "years": dict(years), "external_spam": bool(items) and sum(1 for i in items if not i["rank"]) >= 0.8 * len(items)}

    med_d = bl.median([c.get("dofollow_change") for c in C.values()])
    med_t = bl.median([c.get("traffic_change") for c in C.values()])
    for d, c in C.items():
        c["dofollow_rel"] = c["dofollow_change"] - med_d if c.get("dofollow_change") is not None and med_d is not None else None
        c["traffic_rel"] = c["traffic_change"] - med_t if c.get("traffic_change") is not None and med_t is not None else None

    pages = fetch_pages.collect(run, cands)
    flags, verdicts, excluded = {}, {}, set()
    for d, m in D.items():
        F = [tuple(f) for f in m["flags"]]
        if d in C:
            F = rules.resolve_ext(F, pages.get(d)) + rules.stage2_flags(C[d], pages.get(d))
            if (pages.get(d) or {}).get("home", {}).get("status") == 403 and "unverified_403" not in {c for c, _ in F}:
                F.append(("unverified_403", "сайт віддає 403: вихідні посилання не перевірено, максимум «умовно»"))
        flags[d] = F
        verdicts[d] = rules.verdict_auto(F, m, market, m["type"] == "ринок", notes.get(d))
        if {c for c, _ in F} & rules.EXCLUDE:
            excluded.add(d)
    order, rec = rules.priority(D, verdicts, excluded, set(cands), market, int(inp["recommend"]))
    bal1 = run.balance("after_stage2") if need else None
    run.save("stage2.json", {"candidates": cands, "data": C, "median_dofollow_change": med_d, "median_traffic_change": med_t, "flags": flags, "verdict_auto": verdicts,
                             "excluded_auto": sorted(excluded), "order_auto": order, "recommendation_auto": rec, "cache_hits": run.hits,
                             "missing": [list(x) for x in run.missing], "balance": {"before": bal0, "after": bal1}})

    print(f"\nЕТАП 2 — {run.name}: {len(cands)} кандидатів; медіана dofollow-донорів {med_d:+.0f}%" + (f", медіана трафіку {med_t:+.0f}%" if med_t is not None else ""))
    for d in order:
        c = C.get(d)
        line = f"{rec[d]:<16} {d:<22} {verdicts[d]:<9}"
        if c:
            line += f" dofollow {c.get('dofollow_first')}→{c.get('dofollow_last')} ({c['dofollow_change']:+.0f}%, {c['dofollow_rel']:+.0f} п.п.)" if c.get("dofollow_change") is not None else ""
            line += f" | трафік {c['traffic_change']:+.0f}% ({c['traffic_rel']:+.0f} п.п.)" if c.get("traffic_change") is not None else ""
        print(line)
        for code, text in flags[d]:
            print(f"      [{code}] {text}")
    led = [r for r in run.ledger() if r["stage"] == S]
    print(f"Витрата етапу 2 за полями cost: {sum(r['cost'] for r in led):.6f} $" + (f"; за балансом: {bal0 - bal1:.6f} $ ({bal0} → {bal1})" if bal0 is not None and bal1 is not None else "; баланс не знімався (усе з кешу або офлайн)"))
    print("Далі: заповни verdicts.json (verdict, reason; override_reason, якщо verdict ≠ verdict_auto) і запусти build_report.py")


if __name__ == "__main__":
    main()
