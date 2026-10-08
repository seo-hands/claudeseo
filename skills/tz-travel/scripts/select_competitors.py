#!/usr/bin/env python3
"""Step a: competitor pages for the target page, from the stage-1 SERP cache (no API calls).

python select_competitors.py --workdir . --page <URL> [--types "хаб країни|хаб регіону"] [--refresh]
python select_competitors.py --workdir . --page <URL> --confirm          # after the user approved (or edited) the list

Main keyword + N most frequent adjacent keywords of the page -> TOP-10 pages of the landing type stage 1 found for
this page.  All pages of the main keyword, then the best positions of the adjacent ones, up to the limit.
Search-result URLs with filter parameters are dropped.  Reserves: same landing type first, then keywords without a
neighbour page's head word, then position.  Writes competitors-<slug>.selection.json; analysis needs "confirmed": true.
"""
import argparse, os, re
from urllib.parse import urlsplit, parse_qsl

import tz_common as tz


def filter_url(u):
    q = parse_qsl(urlsplit(u).query)
    return len(q) >= 2 or any(k.lower() in ("departuredate", "returndate", "adults", "duration", "page", "sort", "pricemax") for k, _ in q)


def main():
    ap = tz.args_page(argparse.ArgumentParser())
    ap.add_argument("--types", help="типи посадкових через | (за замовчуванням — тип сторінки з етапу 1)")
    ap.add_argument("--refresh", action="store_true", help="перебудувати список, навіть якщо він уже є")
    ap.add_argument("--confirm", action="store_true", help="позначити список підтвердженим користувачем")
    a = ap.parse_args()
    ctx = tz.load_ctx(a.workdir, a.page)
    f, cfg = ctx["f"]["selection"], ctx["cfg"]
    if os.path.exists(f) and not a.refresh:
        sel = tz.rjson(f)
        if a.confirm:
            sel["confirmed"] = True
            tz.wjson(f, sel)
        show(sel, f)
        return
    types = [t.strip() for t in (a.types or ctx["landing_type"] or "").split("|") if t.strip()]
    if not types:
        tz.die("етап 1 не визначив тип посадкових для цієї сторінки; задайте --types.")
    serps = tz.load_serps(a.workdir)
    keys = [k for k in ctx["keys"] if k["keyword"] != ctx["main"]]
    adjacent = keys[:cfg["adjacent_keywords"]]
    extra = keys[cfg["adjacent_keywords"]:]
    forming = [{"keyword": ctx["main"], "volume": next(k["volume"] for k in ctx["keys"] if k["keyword"] == ctx["main"]), "role": "головний"}] + \
              [{"keyword": k["keyword"], "volume": k["volume"], "role": "суміжний"} for k in adjacent]
    for k in forming:
        k["head_word_of_other_page"] = tz.flag_keyword(ctx, k["keyword"])
        k["in_serp_cache"] = k["keyword"] in serps
        k["type_pages_in_top"] = sum(1 for _, u, _ in serps.get(k["keyword"], []) if ctx["url_type"].get((k["keyword"], u)) in types)
    regions = dict(ctx["S"].get("regions") or {})

    cand, excluded = {}, []

    def collect(kws, tier):
        for k in kws:
            for pos, u, title in serps.get(k["keyword"], []):
                t = ctx["url_type"].get((k["keyword"], u))
                if t not in types or tz.host(u) == tz.host(ctx["S"]["site"]):
                    continue
                if filter_url(u):
                    if u not in [e["url"] for e in excluded]:
                        excluded.append({"url": u, "keyword": k["keyword"], "position": pos, "reason": "URL результатів пошуку з фільтрами в параметрах"})
                    continue
                c = cand.setdefault(u, {"url": u, "type": t, "positions": {}, "other_positions": {}, "tier": tier, "serp_title": title})
                c["positions" if tier == 0 else "other_positions"][k["keyword"]] = pos
    collect(forming, 0)
    collect([{"keyword": k["keyword"]} for k in extra], 1)   # only as further reserves
    flagged = {k["keyword"] for k in forming if k["head_word_of_other_page"]}
    for c in cand.values():
        c["best_position"] = min((c["positions"] or c["other_positions"]).values())
        c["only_flagged_keys"] = bool(c["positions"]) and all(k in flagged for k in c["positions"])
        path = urlsplit(c["url"]).path.lower()
        hub = (ctx["S"].get("hub_slugs") or "").split("|")
        reg = next((n for n, rx in regions.items() if re.search(rx, path)), None)
        if types == ["хаб країни"] and (reg or re.search(r"riviera|aegaeis|ägäis|kueste|küste", path)) and not path.rstrip("/").split("/")[-1] in hub:
            c["note"] = "сторінка регіону, а не країни (етап 1 зарахував до хабів країни)"
    main_urls = [c for c in cand.values() if ctx["main"] in c["positions"]]
    main_urls.sort(key=lambda c: c["positions"][ctx["main"]])
    rest = sorted([c for c in cand.values() if ctx["main"] not in c["positions"] and c["tier"] == 0], key=lambda c: (c["best_position"], c["only_flagged_keys"]))
    selected = (main_urls + rest)[:cfg["competitors_limit"]]
    chosen = {c["url"] for c in selected}
    # reserves: same landing type (all candidates are), then keys without another page's head word, then position
    reserves = sorted([c for c in cand.values() if c["url"] not in chosen], key=lambda c: (c["tier"], c["only_flagged_keys"], c["best_position"]))
    clean = lambda c: {k: v for k, v in c.items() if k not in ("tier",)}
    sel = {"page": ctx["url"], "slug": ctx["slug"], "main_keyword": ctx["main"], "landing_types": types, "forming_keywords": forming,
           "selected": [clean(c) for c in selected], "reserves": [clean(c) for c in reserves[:max(cfg["reserves_min"], 6)]],
           "excluded": excluded, "confirmed": bool(a.confirm),
           "_note": "Покажіть список користувачу. Після підтвердження (або правок у цьому файлі) запустіть select_competitors.py --confirm."}
    tz.wjson(f, sel)
    show(sel, f)


def show(sel, f):
    print(f"Сторінка: {sel['page']} | тип посадкових: {', '.join(sel['landing_types'])}")
    print("Ключі, що формують список:")
    for k in sel["forming_keywords"]:
        flag = f"  [містить головне слово іншої сторінки: {k['head_word_of_other_page']} — лише для близькості, не в title/H1]" if k.get("head_word_of_other_page") else ""
        miss = "" if k.get("in_serp_cache", True) else "  [SERP немає в кеші етапу 1]"
        print(f"  {k['role']:<9} {k['volume']:>6}  {k['keyword']}  (сторінок цього типу в ТОП: {k.get('type_pages_in_top', '?')}){flag}{miss}")
    for title, key in (("Конкуренти", "selected"), ("Запасні (у цьому порядку)", "reserves")):
        print(f"{title} ({len(sel[key])}):")
        for i, c in enumerate(sel[key], 1):
            pos = "; ".join(f"{k} — {v}" for k, v in sorted((c["positions"] or c.get("other_positions", {})).items(), key=lambda x: x[1]))
            print(f"  {i:>2}. {c['url']}  [{pos}]" + (f"  ! {c['note']}" if c.get("note") else ""))
    for e in sel["excluded"]:
        print(f"Відкинуто: {e['url'][:90]}  ({e['keyword']}, поз. {e['position']}) — {e['reason']}")
    print(("ПІДТВЕРДЖЕНО" if sel.get("confirmed") else "НЕ ПІДТВЕРДЖЕНО: покажіть список користувачу, потім --confirm") + f" | {f}")


if __name__ == "__main__":
    main()
