#!/usr/bin/env python3
"""Stage 1 (all domains): summary, spam score, market traffic per language, total traffic for domains outside the
market TLD, donors of the acceptor, three short site: queries through the SERP queue; then prices per 1K traffic,
flags, verdict_auto and the candidates for stage 2.  Writes stage1.json.  Without --yes only prints the estimate."""
import hashlib, sys
import bl_common as bl
import rules

S = "1"


def organic(metrics):
    m = (metrics or {}).get("organic") or {}
    return {"etv": round(m.get("etv") or 0), "count": m.get("count") or 0, "top10": (m.get("pos_1") or 0) + (m.get("pos_2_3") or 0) + (m.get("pos_4_10") or 0)}


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--no-stop", action="store_true", help="не зупинятися після етапу 1: кандидати = candidates_auto")
    a = ap.parse_args()
    if not a.run:
        sys.exit("потрібен --run")
    run = bl.Run(a)
    if not run.input or run.load("stage0.json") is None:
        sys.exit("Спершу stage0.py --input <файл>")
    market, inp = run.market, run.input
    doms = [d["domain"] for d in inp["domains"]]
    prices = {d["domain"]: d["price"] for d in inp["domains"]}
    langs = bl.market_langs(run)
    s0 = run.load("stage0.json")
    notes = run.load("site-notes.json", {})

    P = bl.plan_stage1(run)
    need = [p for p in P if not p["cached"] and not p["domain"].startswith("(")]
    if need:
        bl.print_plan(P, run.budget, run.spent(), show_missing=run.offline)
        if run.offline:
            sys.exit("Офлайн: у кеші бракує відповідей етапу 1 (список вище) — платних запитів не виконано.")
        if not run.yes:
            sys.exit("Це кошторис. Для платних запитів додай --yes.")
    bal0 = run.balance("before_stage1") if need else None
    run.hits = {}

    # 1. spam score: one request for the domains that are not covered by a cached answer
    sc = bl.spam_scores(run)
    miss = [d for d in doms if d not in sc]
    if miss:
        key = "_list-" + hashlib.md5(",".join(sorted(miss)).encode()).hexdigest()[:6]
        run.call(S, key, bl.EP_SPAM, "backlinks/bulk_spam_score/live", {"targets": miss}, "backlinks_bulk_spam_score", len(miss))
        sc = bl.spam_scores(run)
    else:
        run.hits[bl.EP_SPAM] = 1

    D = {}
    for d in doms:
        tld = bl.is_market_tld(d, market)
        x = bl.result(run.call(S, d, bl.EP_SUMMARY, "backlinks/summary/live", {"target": d, "include_subdomains": True, "exclude_internal_backlinks": True}, "backlinks_summary"))
        rd, nf = x.get("referring_domains") or 0, x.get("referring_domains_nofollow") or 0
        pages, ext, broken = x.get("crawled_pages") or 0, x.get("external_links_count"), x.get("broken_pages") or 0
        reliable = bool(pages) and ext is not None and broken / pages <= 0.5
        zone, zone_n = bl.spam_zone(x)
        m = D[d] = {"price": prices[d], "type": "ринок" if tld else "загальний", "spam": sc.get(d), "rank": x.get("rank"), "rd": rd, "rd_nofollow": nf, "dofollow": rd - nf,
                    "main": x.get("referring_main_domains"), "backlinks": x.get("backlinks"), "ips": x.get("referring_ips"), "subnets": x.get("referring_subnets"),
                    "pages": pages, "ext": ext, "broken_pages": broken, "ext_per_page": round(ext / pages, 1) if reliable else None,
                    "ext_note": "" if reliable else ("лічильник зовнішніх посилань недостовірний: більшість сторінок у Backlinks API позначені як биті" if pages and ext is not None else "немає даних"),
                    "diversity": round((x.get("referring_subnets") or 0) / rd, 2) if rd else None, "dofollow_share": round(100 * (rd - nf) / rd, 1) if rd else None,
                    "tld_top": x.get("referring_links_tld") or {}, "first_seen": (x.get("first_seen") or "")[:10], "spam_zone": zone, "spam_zone_links": zone_n, "market": {}}
        for lg in langs:
            r = run.call(S, d, bl.ep_overview(run, lg), "dataforseo_labs/google/domain_rank_overview/live",
                         {"target": d, "location_code": market["location_code"], "language_code": lg, "ignore_synonyms": True}, "labs_domain_rank_overview")
            items = bl.result(r).get("items") or []
            m["market"][lg] = organic(items[0].get("metrics")) if items else {"etv": 0, "count": 0, "top10": 0}
        m["market_etv"] = sum(v["etv"] for v in m["market"].values())
        m["top10"] = sum(v["top10"] for v in m["market"].values())
        dom_lang = max(m["market"], key=lambda k: m["market"][k]["etv"]) if m["market"] else None
        m["dominant_lang"] = dom_lang
        m["lang_share"] = {k: round(100 * v["etv"] / m["market_etv"], 1) if m["market_etv"] else 0 for k, v in m["market"].items()}
        m["world"], m["total_etv"], m["market_share"], m["audience"] = [], None, None, None
        if not tld:
            r = run.call(S, d, bl.EP_ALL, "dataforseo_labs/google/domain_rank_overview/live", {"target": d, "ignore_synonyms": True}, "labs_domain_rank_overview_all")
            rows = [dict(loc=i.get("location_code"), lang=i.get("language_code"), **organic(i.get("metrics"))) for i in bl.result(r).get("items") or []]
            rows.sort(key=lambda v: -v["etv"])
            m["world"] = rows
            m["total_etv"] = sum(v["etv"] for v in rows)
            if m["total_etv"]:
                m["market_share"] = round(100 * sum(v["etv"] for v in rows if v["loc"] == market["location_code"]) / m["total_etv"], 1)
                by_loc = {}
                for v in rows:
                    by_loc[v["loc"]] = by_loc.get(v["loc"], 0) + v["etv"]
                top = max(by_loc, key=by_loc.get)
                m["audience"] = {"loc": top, "etv": by_loc[top], "share": round(100 * by_loc[top] / m["total_etv"], 1), "langs": [v["lang"] for v in rows if v["loc"] == top][:2]}
        p = m["price"]
        m["price_per_1k_market"] = round(p / (m["market_etv"] / 1000)) if p is not None and m["market_etv"] >= 30 else None
        m["price_per_1k_total"] = round(p / (m["total_etv"] / 1000)) if p is not None and m["total_etv"] else None

    # donors of the acceptor: no filter in the request, local filter
    acc = inp["acceptor"]
    run.call(S, acc, bl.EP_REF, "backlinks/referring_domains/live", {"target": acc, "limit": 1000, "order_by": ["rank,desc"]}, "backlinks_referring_domains", 1000)
    hits, acc_info = bl.acceptor_hits(run, doms)
    for d in doms:
        D[d]["links_to_acceptor"] = []
    for d in (hits or {}):
        r = run.call(S, d, bl.EP_LINK, "backlinks/backlinks/live", {"target": acc, "filters": ["domain_from", "=", d], "limit": 10, "mode": "as_is"}, "backlinks_backlinks", 1)
        items = bl.result(r).get("items") or []
        D[d]["links_to_acceptor"] = [{"url_from": i.get("url_from"), "url_to": i.get("url_to"), "anchor": i.get("anchor"), "rel": "dofollow" if i.get("dofollow") else "nofollow",
                                      "first_seen": (i.get("first_seen") or "")[:10], "page_title": i.get("page_from_title"), "location": i.get("semantic_location"),
                                      "text_pre": (i.get("text_pre") or "")[-160:], "page_external_links": i.get("page_from_external_links")} for i in items] or \
                                    [{"url_from": "", "note": "донор є у списку, але запит із точним фільтром нічого не повернув — нулю не вірити, перевірити вручну", "rel": "", "anchor": "", "first_seen": hits[d][0]["first_seen"]}]

    # SERP through the queue
    serp = bl.serp_tasks(run, S)
    for d in doms:
        D[d]["serp"] = serp[d]
        D[d]["casino_pr"] = sum(1 for i in serp[d].get("casino", {}).get("own", []) if bl.is_risky_pr(i, "казино/ставки"))
        D[d]["credit_pr"] = sum(1 for i in serp[d].get("credit", {}).get("own", []) if bl.is_risky_pr(i, "кредити/фінанси"))

    ext_median = bl.median([m["ext_per_page"] for m in D.values()])
    for d in doms:
        m = D[d]
        m["previous"] = s0["previous"].get(d)
        m["placements"] = s0["placements"].get(d, [])
        m["flags"] = rules.stage1_flags(m, market, ext_median)
        if (notes.get(d) or {}).get("status") == 403:
            m["flags"].append(("unverified_403", "сайт віддає 403: вихідні посилання не перевірено, максимум «умовно»"))
        m["verdict_auto"] = rules.verdict_auto(m["flags"], m, market, m["type"] == "ринок", notes.get(d))
    cands = rules.candidates_auto(D, market, int(inp["recommend"]), notes)
    sifted = {}
    for d in doms:
        if d in cands:
            continue
        codes = {c: t for c, t in D[d]["flags"]}
        sifted[d] = codes.get("casino_serp") or codes.get("near_zero") or codes.get("low_traffic") or "слабший за кандидатів за трафіком ринку, рангом і dofollow-донорами"
    bal1 = run.balance("after_stage1") if need else None
    out = {"domains": D, "acceptor": acc_info, "ext_median": ext_median, "candidates_auto": cands, "sifted": sifted, "cache_hits": run.hits,
           "missing": [list(x) for x in run.missing], "balance": {"before": bal0, "after": bal1}}
    if a.no_stop:
        out["candidates"] = cands
    else:
        prev = run.load("stage1.json") or {}
        if prev.get("candidates"):
            out["candidates"] = prev["candidates"]
    run.save("stage1.json", out)

    print(f"\nЕТАП 1 — {run.name}: {len(doms)} доменів, ринок {market['names'][0]}, мови {', '.join(langs)}")
    print(f"{'домен':<22}{'тип':<10}{'ціна':>7}{'ранг':>6}{'spam':>6}{'dofollow':>9}{'трафік':>8}{'заг.':>9}{'частка':>7}{'грн/1K':>8}{'грн/1Kзаг':>10}  казино/кредит PR  вердикт auto")
    for d in doms:
        m = D[d]
        cas = m["serp"].get("casino", {}).get("state")
        print(f"{d:<22}{m['type']:<10}{str(m['price'] if m['price'] is not None else '—'):>7}{str(m['rank']):>6}{str(m['spam']):>6}{m['dofollow']:>9}{m['market_etv']:>8}"
              f"{str(m['total_etv'] if m['total_etv'] is not None else '—'):>9}{str(m['market_share'] if m['market_share'] is not None else '—'):>7}"
              f"{str(m['price_per_1k_market'] or '—'):>8}{str(m['price_per_1k_total'] or '—'):>10}  {(str(m['casino_pr']) + '/10') if cas == 'ok' else cas}; {m['credit_pr']}/10  {m['verdict_auto']}")
    if acc_info:
        print(f"Донори акцептора: отримано {acc_info['returned']} з {acc_info['total']} (з рангом > 0: {acc_info['rank_gt0']}); вже посилаються: {', '.join(hits) if hits else 'ніхто'}")
    for d in (hits or {}):
        for l in D[d]["links_to_acceptor"]:
            print(f"  {d}: {l.get('url_from')} → {l.get('url_to', '')} | анкор: {l.get('anchor')} | {l.get('rel')} | {l.get('first_seen')}")
    print(f"Кандидати auto (N+1 = {len(cands)}): {', '.join(cands)}")
    for d, why in sifted.items():
        print(f"  відсіяно {d}: {why}")
    if run.missing:
        print(f"Не отримано: {len(run.missing)} відповідей — " + "; ".join(f"{x[0]} {x[1]}" for x in run.missing[:8]))
    led = [r for r in run.ledger() if r["stage"] == S]
    print(f"Витрата етапу 1 за полями cost: {sum(r['cost'] for r in led):.6f} $" + (f"; за балансом: {bal0 - bal1:.6f} $ ({bal0} → {bal1})" if bal0 is not None and bal1 is not None else "; баланс не знімався (усе з кешу або офлайн)"))
    print("Продовжую без зупинки (--no-stop): кандидати = candidates_auto." if a.no_stop else
          "СТОП: покажи проміжну таблицю, кандидатів і відсіяних; після підтвердження — stage2.py --candidates <список> --yes")


if __name__ == "__main__":
    main()
