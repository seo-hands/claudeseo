#!/usr/bin/env python3
"""Checks verdicts.json against the rules and builds donors-<acceptor>-<date>.xlsx from the JSON files of the run.
Nothing is typed into the workbook by hand: numbers come from stage1/stage2/pages, judgements from site-notes.json and
verdicts.json.  The build fails when a verdict differs from verdict_auto without override_reason."""
import collections, os, re, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
import bl_common as bl
import rules

NA1 = "не перевірялось — відсіяно на етапі 1"
NA2 = "не запитувалось — домен не з TLD ринку, скорочений обсяг етапу 2"
HEAD = ["домен", "рекомендація", "вердикт", "головна причина", "тип домену (TLD ринку / загальний)", "ціна, грн", "ціна за 1K трафіку ринку, грн", "ціна за 1K загального трафіку, грн",
        "домени-донори", "ранг", "spam score", "тренд профілю 12 міс (dofollow)", "трафік/міс ринку", "загальний трафік", "частка ринку, %", "країна аудиторії",
        "ключів у ТОП-10 (ринок)", "тренд трафіку 12 міс", "тренд відносно медіани", "вихідні посилання і продаж", "частка ризикових ніш у PR", "тематика", "топ-сторінки",
        "вже посилається на акцептор", "розміщувались раніше", "перевірявся раніше", "примітка", "вердикт за правилами (auto)", "причина розбіжності"]


def rec_num(s):
    m = re.match(r"РОЗМІСТИТИ #(\d+)", s or "")
    return int(m.group(1)) if m else None


def validate(run, s1, s2, V):
    inp, market, D = run.input, run.market, s1["domains"]
    n, errs, div = int(inp["recommend"]), [], []
    VD = V.get("domains") or {}
    nums = []
    for d in D:
        v = VD.get(d)
        if not v:
            errs.append(f"{d}: немає запису у verdicts.json")
            continue
        auto, rec_auto = s2["verdict_auto"][d], s2["recommendation_auto"][d]
        if v.get("verdict") not in bl.VERDICTS:
            errs.append(f"{d}: verdict має бути одним із {bl.VERDICTS}")
        reason = (v.get("reason") or "").strip()
        if not reason or "\n" in reason or not re.search(r"\d", reason):
            errs.append(f"{d}: reason — одна фраза з цифрою")
        if v.get("verdict") != auto:
            if not (v.get("override_reason") or "").strip():
                errs.append(f"{d}: verdict «{v.get('verdict')}» ≠ verdict_auto «{auto}» — потрібне поле override_reason")
            div.append((d, "вердикт", auto, v.get("verdict"), v.get("override_reason") or ""))
        rec = v.get("recommendation") or rec_auto
        v["recommendation"] = rec
        if not re.match(r"^(РОЗМІСТИТИ #\d+|РОЗМІСТИТИ — умовно|резерв|не брати)", rec):
            errs.append(f"{d}: recommendation «{rec}» — дозволено «РОЗМІСТИТИ #n», «РОЗМІСТИТИ — умовно, перевірити вручну», «резерв», «не брати»")
        if rec.split(" — ")[0] != rec_auto.split(" — ")[0]:
            div.append((d, "рекомендація", rec_auto, rec, v.get("override_reason") or v.get("note") or ""))
        k = rec_num(rec)
        codes = {c for c, _ in s2["flags"][d]}
        if rec.startswith("РОЗМІСТИТИ"):
            if d not in s2["candidates"]:
                errs.append(f"{d}: рекомендувати можна лише кандидата етапу 2")
            if k and "unverified_403" in codes:
                errs.append(f"{d}: сайт із 403 без перевірки статей — максимум «РОЗМІСТИТИ — умовно, перевірити вручну»")
            if codes & rules.EXCLUDE and not (v.get("override_reason") or "").strip():
                errs.append(f"{d}: правила кажуть «не брати» ({', '.join(codes & rules.EXCLUDE)}) — потрібне поле override_reason")
        if k:
            nums.append((k, d))
    ks = sorted(k for k, _ in nums)
    if ks != list(range(1, len(ks) + 1)):
        errs.append(f"номери рекомендацій мають іти 1…{len(ks)} без пропусків і повторів: {ks}")
    if len(ks) > n:
        errs.append(f"рекомендовано {len(ks)}, а просили {n}")
    general = [d for _, d in nums if not bl.is_market_tld(d, market)]
    if len(general) > n // 2:
        errs.append(f"доменів не з TLD ринку серед рекомендованих {len(general)} — дозволено не більше половини N ({n // 2})")
    return errs, div


def style(ws, widths, wrap=True, money=False, rows=None):
    fill = PatternFill("solid", fgColor="1F3864")
    for c in ws[1]:
        c.fill, c.font, c.alignment = fill, Font(bold=True, color="FFFFFF"), Alignment(wrap_text=True, vertical="center")
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=wrap, vertical="top")
            if isinstance(c.value, bool):
                continue
            if isinstance(c.value, int):
                c.number_format = "#,##0"
            elif isinstance(c.value, float):
                c.number_format = "0.0000" if money else "#,##0.0"
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{rows or ws.max_row}"


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="куди записати xlsx (за замовчуванням <workdir>/donors-<акцептор>-<дата>.xlsx)")
    ap.add_argument("--no-journal", action="store_true", help="не дописувати рядок у журнал CLAUDE.md (тести)")
    ap.add_argument("--check", action="store_true", help="лише перевірити verdicts.json")
    a = ap.parse_args()
    if not a.run:
        sys.exit("потрібен --run")
    run = bl.Run(a)
    s0, s1, s2 = run.load("stage0.json"), run.load("stage1.json"), run.load("stage2.json")
    pages, notes, V = run.load("pages.json", {}), run.load("site-notes.json", {}), run.load("verdicts.json")
    if not (s0 and s1 and s2):
        sys.exit("Потрібні stage0.json, stage1.json і stage2.json")
    if not V:
        tpl = {"domains": {d: {"verdict": s2["verdict_auto"][d], "reason": "", "recommendation": s2["recommendation_auto"][d], "override_reason": "", "outgoing": "", "risky_share": "", "note": ""}
                           for d in s2["order_auto"]}, "anomalies": [], "not_verified": [], "rules_proposals": []}
        run.save("verdicts.json", tpl)
        sys.exit(f"Створено чернетку {run.path('verdicts.json')} з verdict_auto: заповни reason (одна фраза з цифрою), за потреби зміни verdict і recommendation, потім запусти ще раз.")
    inp, market, D, C = run.input, run.market, s1["domains"], s2["data"]
    errs, div = validate(run, s1, s2, V)
    if errs:
        print("verdicts.json не пройшов перевірку:")
        for e in errs:
            print("  - " + e)
        sys.exit(2)
    if a.check:
        print("verdicts.json пройшов перевірку")
    VD = V["domains"]
    _, loc_names = bl.labs_languages(run)
    mk = market["names"][0].capitalize()

    def sort_key(d):
        r = VD[d]["recommendation"]
        k = rec_num(r)
        return (0, k) if k else ((1, 0) if r.startswith("РОЗМІСТИТИ") else (2, 0) if r.startswith("резерв") else (3, s2["order_auto"].index(d)))
    order = sorted(D, key=sort_key)
    recommended = [d for d in order if VD[d]["recommendation"].startswith("РОЗМІСТИТИ")]

    wb = Workbook()
    ws = wb.active
    ws.title = "Зведена"
    ws.append(HEAD)
    green = PatternFill("solid", fgColor="C6EFCE")
    for d in order:
        m, v, n, c, p = D[d], VD[d], notes.get(d) or {}, C.get(d), pages.get(d) or {}
        tld = m["type"] == "ринок"
        if c and c.get("dofollow_change") is not None:
            prof = (f"dofollow-донори {c['dofollow_change']:+.0f}% ({c['dofollow_first']} → {c['dofollow_last']}); відносно медіани кандидатів ({s2['median_dofollow_change']:+.0f}%): "
                    f"{c['dofollow_rel']:+.0f} п.п.; усі донори {c['ts'][0]['rd']} → {c['ts'][-1]['rd']}")
        else:
            prof = NA1
        if c and c.get("hist"):
            h = c["hist"]
            tr = f"трафік {c['traffic_change']:+.0f}% ({h[0]['etv']} → {h[-1]['etv']}, {c['lang']}); ТОП-10 {h[0]['top10']} → {h[-1]['top10']}"
            rel = f"{c['traffic_rel']:+.0f} п.п. (медіана кандидатів з історією {s2['median_traffic_change']:+.0f}%)"
            top = "\n".join(f"{x['etv']} — {x['url']}" for x in c.get("top_pages", [])) + f"\nключів за тематикою «{inp['theme']}» у топ-100: {c.get('theme_kws', 0)}"
        else:
            tr = rel = top = NA2 if c else NA1
        aud = n.get("audience") or ""
        if m.get("audience"):
            au = m["audience"]
            aud = (aud + "; " if aud else "") + f"за трафіком: {loc_names.get(au['loc'], au['loc'])} {au['share']}% ({', '.join(au['langs'])}); Росії в Labs немає"
        lst = p.get("listing")
        risky = v.get("risky_share") or (f"{lst['risky']} з {len(lst['items'])} останніх матеріалів рекламного розділу ({lst['risky_share'] * 100:.0f}%)" if lst and lst.get("items") else
                                         ("рекламного розділу зі списком немає — частку не визначено" if c else NA1))
        outgoing = v.get("outgoing") or ((f"{m['ext_per_page']} зовнішнього посилання на сторінку" if m.get("ext_per_page") is not None else m.get("ext_note", "")) + ("" if c else ". " + NA1))
        if m["links_to_acceptor"]:
            l = m["links_to_acceptor"][0]
            link = f"так — {l.get('url_from')} → {l.get('url_to', '')}, {l.get('rel')}, анкор: {l.get('anchor')}, з {l.get('first_seen')}" if l.get("url_from") else "так — " + l.get("note", "")
        else:
            ai = s1.get("acceptor") or {}
            link = f"ні ({ai.get('returned')} донорів акцептора з {ai.get('total')}, усі {ai.get('rank_gt0')} з рангом > 0)" if ai else "не перевірено"
        pl = m.get("placements") or []
        placed = "; ".join(f"{x['date']}, {x['status']}, {x['price']} {x['currency'] or ''}".strip() + (" — ВЖЕ В РОБОТІ" if x["in_work"] else "") for x in pl) if pl else (n.get("placed") or "ні")
        prev = f"так — {m['previous']['date']}, вердикт «{m['previous']['verdict']}» ({m['previous']['file']})" if m.get("previous") else "ні"
        topic = n.get("topic") or ""
        if n.get("status") == 403:
            topic = (topic + " " if topic else "") + "Головна віддає 403 — тематику не перевірено."
        ws.append([d, v["recommendation"], v["verdict"], v["reason"], "TLD ринку" if tld else "загальний", m["price"],
                   m["price_per_1k_market"] if m["price_per_1k_market"] is not None else ("не застосовно" if m["price"] is not None else None),
                   m["price_per_1k_total"] if m["price_per_1k_total"] is not None else (f"не запитувалось (TLD ринку)" if tld else None),
                   m["rd"], m["rank"], m["spam"], prof, m["market_etv"], m["total_etv"] if m["total_etv"] is not None else "не запитувалось (TLD ринку)",
                   m["market_share"] if m["market_share"] is not None else "не запитувалось (TLD ринку)", aud, m["top10"], tr, rel, outgoing, risky, topic, top, link, placed, prev,
                   v.get("note") or "", s2["verdict_auto"][d], v.get("override_reason") or ""])
        if v["recommendation"].startswith("РОЗМІСТИТИ"):
            for cell in ws[ws.max_row]:
                cell.fill = green
    total_price = sum(D[d]["price"] or 0 for d in recommended)
    style(ws, [17, 24, 11, 46, 12, 9, 12, 12, 10, 8, 8, 40, 12, 12, 10, 30, 10, 34, 26, 60, 50, 44, 58, 36, 26, 22, 50, 14, 40], rows=len(order) + 1)
    ws.append([])
    ws.append(["РАЗОМ", f"вартість розміщення на {len(recommended)} рекомендованих", None, ", ".join(recommended), None, total_price])
    for cell in ws[ws.max_row]:
        cell.font, cell.alignment = Font(bold=True), Alignment(wrap_text=True, vertical="top")
    ws.cell(row=ws.max_row, column=6).number_format = "#,##0"

    wm = wb.create_sheet("Метрики")
    wm.append(["домен", "показник", "період / деталь", "значення", "джерело"])
    for d in order:
        m = D[d]
        for name, key, src in [("ранг (0–1000)", "rank", "backlinks_summary"), ("spam score", "spam", "backlinks_bulk_spam_score"), ("домени-донори", "rd", "backlinks_summary"),
                               ("з них nofollow", "rd_nofollow", "backlinks_summary"), ("dofollow-донори", "dofollow", "розрахунок"), ("частка dofollow-донорів, %", "dofollow_share", "розрахунок"),
                               ("основні домени-донори", "main", "backlinks_summary"), ("беклінки", "backlinks", "backlinks_summary"), ("IP донорів", "ips", "backlinks_summary"),
                               ("підмережі донорів", "subnets", "backlinks_summary"), ("різноманітність (підмережі / донори)", "diversity", "розрахунок"),
                               ("просканованих сторінок", "pages", "backlinks_summary"), ("зовнішні посилання з сайту", "ext", "backlinks_summary"), ("битих сторінок", "broken_pages", "backlinks_summary"),
                               ("вихідних на сторінку", "ext_per_page", "розрахунок"), ("трафік ринку, усі мови", "market_etv", "labs domain_rank_overview"), ("ключів у ТОП-10, усі мови", "top10", "labs domain_rank_overview"),
                               ("загальний трафік", "total_etv", "labs domain_rank_overview без location"), ("частка ринку, %", "market_share", "розрахунок")]:
            if m.get(key) is not None:
                wm.append([d, name, run.input["date"][:7], m[key], src])
        for lg, x in m["market"].items():
            wm.append([d, f"трафік ринку ({lg})", f"частка мови {m['lang_share'].get(lg)}%", x["etv"], "labs domain_rank_overview"])
            wm.append([d, f"ключів у ТОП-10 ({lg})", "", x["top10"], "labs domain_rank_overview"])
        for x in m["world"][:8]:
            wm.append([d, "трафік за ринком", f"{loc_names.get(x['loc'], x['loc'])}, {x['lang']}", x["etv"], "labs domain_rank_overview без location"])
        for q, x in m["serp"].items():
            wm.append([d, f"SERP site: {q} — результатів", f"{x['state']}; сторінок домену в топ-10: {len(x['own'])}", x["count"] if x["count"] is not None else "не отримано", "serp task"])
        wm.append([d, "PR казино серед 10 результатів", "", m["casino_pr"], "serp task + правила"])
        wm.append([d, "PR кредитів серед 10 результатів", "", m["credit_pr"], "serp task + правила"])
        c = C.get(d)
        if not c:
            continue
        for x in c["ts"]:
            wm.append([d, "dofollow-донори, помісячно", x["m"], x["dofollow"], "backlinks_timeseries_summary"])
            wm.append([d, "усі донори, помісячно", x["m"], x["rd"], "backlinks_timeseries_summary"])
        for b, n_ in c["buckets"].items():
            wm.append([d, "розподіл топ-100 донорів за рангом", b, n_, "backlinks_referring_domains"])
        for x in c["ref_top10"]:
            wm.append([d, "топ-10 донорів: ранг", x["domain"], x["rank"], "backlinks_referring_domains"])
        for x in c.get("hist", []):
            wm.append([d, f"трафік ринку ({c['lang']}), помісячно", x["m"], x["etv"], "labs historical_rank_overview"])
            wm.append([d, f"ТОП-10 ({c['lang']}), помісячно", x["m"], x["top10"], "labs historical_rank_overview"])
        for k in c.get("kws", [])[:30]:
            wm.append([d, "топ-ключі: трафік", f"{k['keyword']} (поз. {k['pos']})", k["etv"], "labs ranked_keywords"])
        for x in (c.get("zone") or {}).get("items", []):
            wm.append([d, f"донори зони {c['zone']['zone']}: посилань", f"{x['domain']} (ранг {x['rank']}, з {x['first_seen']})", x["backlinks"], "backlinks_referring_domains"])
    style(wm, [17, 42, 46, 16, 38], wrap=False)

    wp = wb.create_sheet("PR і ризики")
    wp.append(["домен", "URL", "тип (PR / ризикова ніша)", "зовнішніх посилань у тілі / у шаблоні", "rel", "тематика цілей"])
    seen = set()
    for d in order:
        p = pages.get(d) or {}
        for x in p.get("articles") or []:
            seen.add(x["url"])
            if x["status"] != 200:
                wp.append([d, x["url"], f"не відкрилась ({x['status']})", "не перевірено", "не перевірено", "не перевірено"])
                continue
            mine = any(l["domain"] == bl.reg_domain(inp["acceptor"]) for l in x["body"])
            typ = "PR — наявне посилання на акцептор" if mine else (("ризикова ніша: " + x["niche"]) if x["niche"] else ("PR" if x["body_n"] else "матеріал без зовнішніх посилань"))
            wp.append([d, x["url"], typ, f"тіло: {x['body_n']}, шаблон: {x['tmpl_n']}" if x["split"] else f"тіло: {x['body_n']}, шаблон не відокремлено",
                       ", ".join(sorted({l["rel"] for l in x["body"]})) or "—", ", ".join(sorted({l["domain"] for l in x["body"]})) or "—"])
        for r in (p.get("home") or {}).get("risky") or []:
            sw = p["home"].get("sitewide")
            wp.append([d, "https://" + d + "/", f"ризикова ніша: {r['niche']} — посилання на головній ({'наскрізне' if sw else 'не наскрізне' if sw is False else 'наскрізність не перевірено'})",
                       "шаблон головної: 1", r["rel"], r["domain"]])
        for x in ((p.get("listing") or {}).get("items") or []):
            if x["url"] in seen:
                continue
            seen.add(x["url"])
            wp.append([d, x["url"], ("ризикова ніша: " + x["niche"]) if x["niche"] else "PR (останні матеріали рекламного розділу)", "не розбиралось", "не розбиралось", x["title"][:90]])
        for q, wanted in (("casino", "казино/ставки"), ("credit", "кредити/фінанси")):
            for x in D[d]["serp"].get(q, {}).get("own", []):
                if x["url"] not in seen and bl.is_risky_pr(x, wanted):
                    seen.add(x["url"])
                    wp.append([d, x["url"], f"ризикова ніша: {wanted} (знайдено пошуком — лише сигнал)", "не розбиралось", "не розбиралось", x["title"][:90]])
    style(wp, [17, 95, 50, 28, 22, 60], wrap=False)

    wc = wb.create_sheet("Витрати")
    wc.append(["ендпоінт", "запитів", "прогноз $", "факт $ (за cost)", "з кешу"])
    led = run.ledger()
    agg = collections.OrderedDict()
    for r in led:
        g = agg.setdefault((r["stage"], r["endpoint"]), [0, 0.0, 0.0])
        g[0] += r.get("requests", 1)
        g[1] += r["est"]
        g[2] += r["cost"]
    hits = {("1", k): v for k, v in (s1.get("cache_hits") or {}).items()}
    hits.update({("2", k): v for k, v in (s2.get("cache_hits") or {}).items()})
    for key in list(agg) + [k for k in hits if k not in agg]:
        n_, est, cost = agg.get(key, [0, 0.0, 0.0])
        wc.append([f"ЕТАП {key[0]} — {key[1]}", n_, round(est, 4), round(cost, 6), hits.get(key, 0)])
    tc = sum(r["cost"] for r in led)
    wc.append(["РАЗОМ за полями cost", sum(g[0] for g in agg.values()), round(sum(g[1] for g in agg.values()), 4), round(tc, 6), sum(hits.values())])
    bals = [b for b in run.balances() if b.get("balance") is not None]
    by_balance = round(bals[0]["balance"] - bals[-1]["balance"], 6) if len(bals) > 1 else None
    wc.append(["РАЗОМ за балансом", None, None, by_balance if by_balance is not None else "баланс не знімався (усе з кешу або офлайн)",
               f"{bals[0]['balance']} → {bals[-1]['balance']} $" if by_balance is not None else ""])
    wc.append([f"Бюджет {run.budget:.2f} $; ціни для прогнозу станом на {bl.PRICES['date']}, запас {int(bl.RESERVE * 100)}%; лічильник плагіна claude-seo прямих запитів не бачить", None, None, None, ""])
    style(wc, [70, 10, 12, 18, 40], money=True)

    wa = wb.create_sheet("Аномалії")
    wa.append(["домен", "аномалія", "дані", "висновок"])
    AUTO = {"spam": "spam score понад поріг", "few_dofollow": "мало dofollow-донорів", "ext_outlier": "вихідних посилань непропорційно багато", "dofollow_trend": "dofollow-донори падають швидше за медіану",
            "traffic_trend": "трафік падає швидше за медіану", "donor_spike": "стрибок dofollow-донорів", "casino_keyword": "казино-запит у топі трафіку", "casino_home": "казино на головній",
            "casino_home_sitewide": "наскрізні посилання на казино", "toxic_pr": "PR токсичної ніші", "risky_share": "висока частка ризикових ніш", "casino_serp": "PR казино у видачі",
            "serp_undetermined": "SERP повернув сторонні сайти", "unverified_403": "сайт віддає 403"}
    for d in order:
        for code, text in s2["flags"][d]:
            if code in AUTO:
                wa.append([d, AUTO[code], text, "прапорець правил (auto)"])
        m, c = D[d], C.get(d)
        if m.get("ext_note") and m["ext"] is not None:
            wa.append([d, "лічильник зовнішніх посилань недостовірний", f"{m['broken_pages']} із {m['pages']} просканованих сторінок позначені як биті", "краулер DataForSEO блокується; вихідних на сторінку не рахуємо"])
        if c and c.get("zone"):
            z = c["zone"]
            wa.append([d, f"посилання із зони {z['zone']}", f"{z['links']} посилань із {z['domains']} доменів; з рангом 0: {z['rank0']} з {len(z['items'])} перевірених; роки появи: {z['years']}",
                       "зовнішній спам (дорвеї з нульовим рангом), не мережа сайту" if z["external_spam"] else "можлива мережа — перевірити вручну"])
        for q, x in m["serp"].items():
            if x["state"] == "не отримано":
                wa.append([d, "SERP-завдання не повернулося з черги", f"запит {q}", "не отримано"])
    if s2.get("median_dofollow_change") is not None:
        wa.append(["усі кандидати", "тренд dofollow-донорів відносно медіани", f"медіана {s2['median_dofollow_change']:+.0f}%: " + "; ".join(f"{d} {C[d]['dofollow_change']:+.0f}%" for d in s2["candidates"] if C[d].get("dofollow_change") is not None),
                   "оцінювати лише відхилення від медіани: зміни по всій базі не говорять про сайт"])
    for x in V.get("anomalies") or []:
        wa.append([x.get("domain", ""), x.get("anomaly", ""), x.get("data", ""), x.get("conclusion", "")])
    for nt in s0.get("notes") or []:
        wa.append(["вхідні дані / ринок", "примітка етапу 0", nt, ""])
    style(wa, [20, 40, 74, 66])

    wr = wb.create_sheet("Ручна перевірка")
    wr.append(["домен", "що відкрити", "на що подивитися", "чому не перевірено автоматично"])
    blocked = [d for d in order if (notes.get(d) or {}).get("status") == 403]
    if not blocked:
        wr.append(["(403 на головній)", "—", "жоден сайт зі списку не віддав 403 на головній", "—"])
    for d in blocked:
        wr.append([d, "https://" + d + "/", "рубрики, розділ подорожей, рекламний розділ, 3 PR-статті: посилання в тілі, rel, тематика цілей", "сайт віддає 403 (Cloudflare) — повторних спроб не було"])
    for d in order:
        for x in (notes.get(d) or {}).get("manual_check") or []:
            wr.append([d, x.get("open", ""), x.get("look", ""), x.get("why", "")])
        for x in (pages.get(d) or {}).get("articles") or []:
            if x["status"] != 200:
                wr.append([d, x["url"], "зовнішні посилання в тілі статті, rel, тематика цілей", f"сторінка не відкрилась ({x['status'] or 'немає в кеші'})"])
    style(wr, [18, 50, 64, 60])

    wq = wb.create_sheet("Параметри")
    wq.append(["параметр", "значення"])
    for k, val in [("акцептор", inp["acceptor"]), ("ринок", mk), ("location_code", market["location_code"]), ("google-домен", market["se_domain"]),
                   ("мови Labs", ", ".join(s0["languages"])), ("тематика", inp["theme"]), ("дата", inp["date"]), ("рекомендувати", int(inp["recommend"])), ("бюджет, $", run.budget),
                   ("доменів", len(D)), ("кандидати етапу 2", ", ".join(s2["candidates"])), ("поріг трафіку ринку", market["min_traffic"]), ("spam score: мінус понад", rules.SPAM_MINUS),
                   ("dofollow-донорів: мінус менше", rules.DOFOLLOW_MIN), ("тренд відносно медіани: мінус нижче, п.п.", rules.REL_TREND_MINUS), ("PR казино у видачі: не брати від", rules.CASINO_SERP_EXCLUDE),
                   ("ризикові ніші в рекламному розділі: мінус від", rules.RISKY_SHARE_MINUS), ("доменів не з TLD ринку серед рекомендованих, не більше", int(inp["recommend"]) // 2),
                   ("ціни DataForSEO станом на", bl.PRICES["date"]), ("TTL кешу, днів", bl.TTL_DAYS)]:
        wq.append([k, val])
    for x in V.get("not_verified") or []:
        wq.append(["не вдалося перевірити", x])
    for x in V.get("rules_proposals") or []:
        wq.append(["пропозиція до rules.md", x])
    style(wq, [52, 110])

    out = a.out or os.path.join(run.workdir, inp["output"])
    try:
        wb.save(out)
    except PermissionError:
        out = re.sub(r"\.xlsx$", ".new.xlsx", out)
        wb.save(out)
        print("Файл відкритий в Excel — записано " + out + "; закрий Excel і повтори запуск.")
    print(f"Збережено: {out}")
    print(f"Рекомендовано {len(recommended)} з {inp['recommend']}: {', '.join(recommended)} | вартість: " + f"{total_price:,.0f} грн".replace(",", " "))
    print(f"Розбіжності verdict / verdict_auto і рекомендацій ({len(div)}) — матеріал для калібрування rules.md:")
    for d, kind, auto, mine, why in div:
        print(f"  {d}: {kind} — auto «{auto}», у verdicts.json «{mine}»" + (f" | причина: {why}" if why else ""))
    if not div:
        print("  немає")
    if not a.no_journal:
        reserve = [d for d in order if VD[d]["recommendation"].startswith("резерв")]
        line = (f"- {inp['date']} — акцептор {inp['acceptor']} ({inp['theme']}, {mk}); {len(D)} доменів: {', '.join(d['domain'] for d in inp['domains'])}; рекомендовано: {', '.join(recommended)}"
                + (f", резерв {', '.join(reserve)}" if reserve else "") + f"; вартість рекомендованих {total_price:,.0f} грн".replace(",", " ")
                + (f"; витрата DataForSEO {by_balance:.3f} $ за балансом".replace(".", ",") if by_balance is not None else f"; витрата DataForSEO {tc:.3f} $ за полями cost".replace(".", ","))
                + f"; файл: {os.path.basename(out)}")
        bl.sp.journal_add(run.workdir, bl.JOURNAL_SECTION, f"{inp['date']} — акцептор {inp['acceptor']} ", line)
        print("Журнал: рядок у " + os.path.join(run.workdir, "CLAUDE.md"))
    return out


if __name__ == "__main__":
    main()
