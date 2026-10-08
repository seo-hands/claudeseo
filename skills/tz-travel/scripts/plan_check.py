#!/usr/bin/env python3
"""Plan of the brief: draft for Claude and the checks every plan must pass before build_tz.py.

python plan_check.py --workdir . --page <URL> --draft     # writes tz-<slug>-plan.draft.json (data + empty fields)
python plan_check.py --workdir . --page <URL>             # checks tz-<slug>-plan.json, exit code 1 on errors

The scripts cannot invent German headings, FAQ questions, meta tags and Ukrainian translations: Claude fills the plan
following references/rules.md, the checks here make the rules binding (see references/plan-schema.md).
"""
import argparse, os, re, sys

import tz_common as tz

BLOCKS = {"faq": ("FAQ", lambda c: c["faq"]["present"], "with_faq"),
          "regions": ("блок регіонів", lambda c: c["regions"]["block"], "with_region_block"),
          "seasons": ("блок сезону", lambda c: c["seasons"]["block"], "with_season_block")}
HEAD_ONLY = "лише заголовок або блок посилань, тексту немає"


def block_text(ctx, own, key):
    """the same "heading + text" rule as for heading clusters: does the own body text really cover the block's topic?"""
    body = own.get("body_text") or ""
    if key == "faq":
        return len(own["faq"]["questions"]) >= 3
    if key == "regions":
        ents = ctx["T"].get("entities", {}).get(ctx["S"]["slug"], []) or list(ctx["S"].get("regions") or {})
        return sum(1 for e in ents if re.search(r"(?<!\w)" + re.escape(e) + r"(?!\w)", body, re.I)) >= 3
    if key == "seasons":
        return sum(1 for m in ctx["T"]["months"] if re.search(r"(?<!\w)" + m + r"(?!\w)", body)) >= 2 or bool(re.search(ctx["T"]["patterns"]["season"], body, re.I))
    return False


def load_data(ctx):
    for k in ("competitors", "embeddings"):
        if not os.path.exists(ctx["f"][k]):
            tz.die(f"немає {ctx['f'][k]}: спершу analyze_competitors.py та embed_terms.py.")
    return tz.rjson(ctx["f"]["competitors"]), tz.rjson(ctx["f"]["embeddings"])


def topics(ctx, C, E):
    """id -> topic with competitor count and gap flag: heading clusters ("subtopic:<label>") and page blocks ("block:faq")"""
    n, own, gmin = C["summary"]["analysed_ok"], C["own"], ctx["cfg"]["gap_min_competitors"]
    out = {}
    for r in E["subtopics"] + E.get("subtopic_singletons", []):
        out["subtopic:" + r["subtopic"]] = {"name": r["subtopic"], "competitors": r["competitors"], "of": n, "gap": r["gap"], "own": r["own_status"], "source": "кластер заголовків"}
    for key, (name, fn, stat) in BLOCKS.items():
        k, head = C["summary"][stat], bool(own.get("ok") and fn(own))
        has = head and block_text(ctx, own, key)
        out["block:" + key] = {"name": name, "competitors": k, "of": n, "gap": k >= gmin and not has,
                               "own": "так" if has else (HEAD_ONLY if head else "ні"), "source": "блок сторінки (розбір HTML)"}
    return out


def info_evidence(ctx, C, rx):
    """competitors that have an H2/H3 on an informational neighbour's topic"""
    return sorted({tz.host(c["url"]) for c in C["competitors"] if c.get("ok") and any(re.search(rx, o["text"], re.I) for o in c["outline"])})


def topic_ids(s):
    t = s.get("topic")
    return [] if not t else ([t] if isinstance(t, str) else list(t))


def rng(c):
    return (int(c[0]), int(c[1])) if c else None


def exact_plan(ctx, plan):
    heads = [s["heading"] for s in plan["structure"] if s["level"] in ("H1", "H2", "H3") and tz.exact_count(ctx["main"], s["heading"])]
    faq = [q["q"] for q in plan["faq"] if tz.exact_count(ctx["main"], q["q"])]
    return heads, faq, list(plan.get("exact_text", []))


def sums(plan):
    blocks = [rng(s["chars"]) for s in plan["structure"] if s["level"] in ("intro", "H2") and s.get("chars")]
    return sum(b[0] for b in blocks), sum(b[1] for b in blocks)


def check(ctx, plan, C, E):
    T, cfg, main = ctx["T"], ctx["cfg"], ctx["main"]
    err, warn = [], []
    S = C["summary"]
    tp = topics(ctx, C, E)
    st = plan.get("structure", [])
    lv = [s["level"] for s in st]

    # --- order of a commercial page: H1 -> 1-2 sentences -> listing -> text starting with an H2
    if plan.get("page_kind", "commercial") == "commercial":
        if lv[:3] != ["H1", "intro", "listing"] or (len(lv) > 3 and lv[3] != "H2"):
            err.append("порядок блоків: має бути H1 → intro (1–2 речення) → listing (без заголовка) → текст, що починається з H2; зараз: " + " → ".join(lv[:4]))
    if lv.count("H1") != 1:
        err.append("у структурі має бути рівно один H1")
    for s in st:
        if s["level"] == "intro" and (not s.get("chars") or rng(s["chars"])[1] > T["intro_max"]):
            err.append(f"вступ під H1 довший за {T['intro_max']} символів")
        if s["level"] in ("H2", "intro") and not s.get("chars"):
            err.append(f"немає обсягу для блоку «{s.get('heading')}»")
    cur, h3 = None, {}
    for s in st:
        if s["level"] == "H2":
            cur = s["heading"]
        elif s["level"] == "H3":
            if cur is None:
                err.append(f"H3 «{s['heading']}» стоїть до першого H2")
            elif s.get("chars"):
                h3.setdefault(cur, [0, 0])
                h3[cur][0] += rng(s["chars"])[0]
                h3[cur][1] += rng(s["chars"])[1]
    for s in st:
        if s["level"] == "H2" and s["heading"] in h3 and h3[s["heading"]][1] > rng(s["chars"])[1]:
            err.append(f"сума H3 ({h3[s['heading']][1]}) більша за обсяг H2 «{s['heading']}» ({rng(s['chars'])[1]})")

    # --- volume: from the competitors' median up to the text leaders of the TOP-5; blocks add up to the declared range
    lo, hi = sums(plan)
    vr = plan.get("volume", {}).get("range")
    if not vr:
        err.append("не задано volume.range")
    else:
        if vr[0] < S["text_median"]:
            err.append(f"нижня межа обсягу {vr[0]} менша за медіану конкурентів {S['text_median']}")
        if vr[1] > S["text_top5"][0]:
            err.append(f"верхня межа обсягу {vr[1]} більша за найдовший текст у ТОП {S['text_top5'][0]}")
        if not (vr[0] <= lo and hi <= vr[1] and lo - vr[0] <= 0.05 * vr[0] and vr[1] - hi <= 0.05 * vr[1]):
            err.append(f"сума обсягів блоків {lo}–{hi} не дорівнює заявленому діапазону {vr[0]}–{vr[1]} (допуск 5 %)")
        if not plan["volume"].get("why"):
            err.append("volume.why: поясніть вибір діапазону (медіана і рівень текстових лідерів)")

    # --- exact form of the main keyword
    heads, faq, text = exact_plan(ctx, plan)
    h1 = next((s["heading"] for s in st if s["level"] == "H1"), "")
    if not tz.exact_count(main, h1):
        err.append(f"H1 має містити точну форму головного ключа «{main}»")
    if any(tz.exact_count(main, s["heading"]) for s in st if s["level"] == "H3"):
        err.append("точна форма головного ключа в H3 заборонена")
    if len(heads) > T["exact_in_headings"]:
        err.append(f"точна форма «{main}» у {len(heads)} заголовках, дозволено {T['exact_in_headings']} (H1 + один H2): " + "; ".join(heads))
    if len(faq) > T["exact_in_faq"]:
        err.append(f"точна форма «{main}» у {len(faq)} питаннях FAQ, дозволено {T['exact_in_faq']}")
    if len(heads) + len(faq) + len(text) > T["exact_limit"]:
        err.append(f"точних входжень «{main}» заплановано {len(heads) + len(faq) + len(text)}, ліміт {T['exact_limit']}")

    # --- head words of neighbour pages are banned in title, H1, H2, H3
    sets = [("A", plan["meta"]["A"])] + [(t.get("name", "тест"), t) for t in plan["meta"].get("tests", [])]
    where = [("заголовок «%s»" % s["heading"], s["heading"]) for s in st if s["level"] in ("H1", "H2", "H3")]
    for name, m in sets:
        where += [(f"title комплекту {name}", m["title"]["text"]), (f"H1 комплекту {name}", m["h1"]["text"])]
    for b in ctx["banned"]:
        for label, text_ in where:
            if re.search(b["match"], text_, re.I):
                err.append(f"головне слово сторінки {b['page']} («{b['label']}») у {label}")

    # --- topics of informational neighbour pages: no own H2 unless >= N competitors have one
    for n in ctx["neighbours"]:
        if n["kind"] != "info":
            continue
        ev = info_evidence(ctx, C, n["match"])
        for s in st:
            if s["level"] == "H2" and re.search(n["match"], s["heading"], re.I) and len(ev) < cfg["gap_min_competitors"]:
                err.append(f"H2 «{s['heading']}» — тема інформаційної сторінки {n['page']}, а окремий заголовок про неї мають лише {len(ev)} конкурентів "
                           f"(потрібно {cfg['gap_min_competitors']}): лишити коротко у FAQ або в кінці блоку з посиланням")

    # --- gaps must be in the structure (or declined with a reason)
    used = {t for s in st for t in topic_ids(s)}
    for u in used:
        if u not in tp:
            err.append(f"structure.topic «{u}» не знайдено серед підтем (див. чернетку: topics)")
    for tid, t in tp.items():
        if t["gap"] and tid not in used and tid not in plan.get("gaps_declined", {}):
            err.append(f"прогалина «{t['name']}» ({t['competitors']} з {t['of']}) не включена в структуру і не відхилена в gaps_declined")

    # --- every stage-1 cluster of the page gets its own H2 or H3, whatever the competitors do
    covered = [c for s in st if s["level"] in ("H2", "H3") for c in s.get("clusters", [])]
    for c in covered:
        if c not in ctx["clusters"]:
            err.append(f"structure.clusters: «{c}» не є кластером цієї сторінки (є: {', '.join(ctx['clusters'])})")
    for cid, c in ctx["clusters"].items():
        if cid not in covered:
            err.append(f"кластер {cid} («{c['head']}», {c['volume']}) не закрито жодним H2 або H3: додайте його в clusters відповідного заголовка")
    if any(s.get("clusters") for s in st if s["level"] not in ("H2", "H3")):
        err.append("clusters можна призначати лише H2 або H3")

    # --- meta tags
    for name, m in sets:
        t, d, h = m["title"]["text"], m["description"]["text"], m["h1"]["text"]
        if len(t) > T["title_max"]:
            err.append(f"title комплекту {name}: {len(t)} символів, ліміт {T['title_max']}")
        if len(d) > T["description_max"]:
            err.append(f"description комплекту {name}: {len(d)} символів, ліміт {T['description_max']}")
        if tz.symbols(t):
            err.append(f"title комплекту {name} містить символи: {' '.join(tz.symbols(t))}")
        sy, ds = tz.symbols(d), T["description_symbols"]
        if set(sy) - set(ds["allowed"]) or len(set(sy)) > ds["max_distinct"] or any(sy.count(x) > ds["max_each"] for x in set(sy)):
            err.append(f"description комплекту {name}: символи {' '.join(sy)} — дозволено не більше {ds['max_distinct']} різних з «{ds['allowed']}», кожен до {ds['max_each']} разів")
        if not t.lower().startswith(main.lower()) or not h.lower().startswith(main.lower()):
            err.append(f"комплект {name}: title і H1 мають починатися з головного ключа — узгодженої пари немає")
    a = plan["meta"]["A"]
    if not a["description"]["text"].lower().startswith(a["h1"]["text"].lower()[:len(main) + 1]) or not a["title"]["text"].lower().startswith(a["h1"]["text"].lower()):
        err.append("комплект A: title, description і H1 мають починатися однаково (title починається з тексту H1)")
    if a["h1"]["text"] != h1:
        err.append("H1 комплекту A не збігається з H1 у структурі")
    if S["title_year"] >= 3 and not re.search(r"\b20[2-3]\d\b", a["title"]["text"]):
        warn.append(f"рік у title мають {S['title_year']} конкурентів, а в title комплекту A року немає")
    for w in S["title_words"]:
        if w["competitors"] > S["analysed_ok"] / 2 and w["word"] not in a["title"]["text"].lower():
            warn.append(f"слово «{w['word']}» є в title у {w['competitors']} з {S['analysed_ok']} конкурентів, а в title комплекту A його немає")
    for t_ in plan["meta"].get("tests", []):
        if not t_.get("condition"):
            err.append(f"тестовий комплект {t_.get('name')}: немає умови, за якої його пробувати")

    # --- keywords, links, terms, data rules
    for k in ctx["keys"]:
        p = plan.get("keywords", {}).get(k["keyword"])
        if not p:
            err.append(f"ключ «{k['keyword']}» без місця в плані")
        elif tz.flag_keyword(ctx, k["keyword"]) and re.search(r"title|H1", p["place"]):
            err.append(f"ключ «{k['keyword']}» містить головне слово іншої сторінки і не може йти в title/H1")
    linked = {l["page"] for l in plan.get("links", [])}
    for n in ctx["neighbours"]:
        if n["page"] not in linked and n["page"] not in plan.get("links_skip", {}):
            err.append(f"сторінка {n['page']} з розподілу етапу 1 не має рядка в links і не пояснена в links_skip")
    for l in plan.get("links", []) + plan.get("links_extra", []):
        if len(l.get("anchors", [])) != 2:
            err.append(f"посилання на {l['page']}: потрібно рівно два анкори")
    tr, skip = plan.get("terms", {}), {x.lower() for x in plan.get("terms_skip", [])}
    for t_ in E["terms"]:
        k = t_["term"].lower()
        if k in tr and not tr[k].get("uk"):
            err.append(f"семантичне слово «{t_['term']}» без перекладу українською")
        if t_["competitors"] >= cfg["gap_min_competitors"] and k not in tr and k not in skip:
            err.append(f"семантичне слово «{t_['term']}» є у {t_['competitors']} конкурентів, але його немає ні в terms, ні в terms_skip")
    cl = T.get("climate")
    for tb in plan.get("tables", []):
        if cl and re.search(cl["match"], tb, re.I) and cl["sources"][0] not in tb:
            err.append(f"таблиця з кліматом без конкретного джерела ({cl['sources'][0]}, резерв {cl['sources'][1]})")
    for key in ("goal", "photos", "faq", "header"):
        if not plan.get(key):
            err.append(f"порожнє поле плану: {key}")
    for tid, t in tp.items():
        if t["gap"] and tid.startswith("subtopic:") and t["name"] not in plan.get("subtopics_uk", {}):
            warn.append(f"підтема-прогалина «{t['name']}» без перекладу в subtopics_uk")
    return err, warn


def draft(ctx, C, E):
    T, S = ctx["T"], C["summary"]
    tp = topics(ctx, C, E)
    return {
        "_readme": "Чернетка плану ТЗ. Заповніть поля за references/rules.md і plan-schema.md, збережіть як tz-<slug>-plan.json, перевірте plan_check.py.",
        "page": ctx["url"], "slug": ctx["slug"], "page_kind": "commercial",
        "_data": {
            "main_keyword": ctx["main"],
            "keywords": [{"keyword": k["keyword"], "translation": k["translation"], "volume": k["volume"], "sim_main": k["sim_main"], "tier_hint": k["tier"],
                          "head_word_of_other_page": k["head_word_of_other_page"]} for k in sorted(E["keywords"], key=lambda r: -r["volume"])],
            "clusters_must_have_own_h2_or_h3": list(ctx["clusters"].values()),
            "banned_in_title_and_headings": ctx["banned"],
            "neighbours": ctx["neighbours"],
            "info_topics_evidence": {n["page"]: len(info_evidence(ctx, C, n["match"])) for n in ctx["neighbours"] if n["kind"] == "info"},
            "volume": {"median": S["text_median"], "top5": S["text_top5"], "own": C["own"].get("text_chars_nospace")},
            "title_formula": {"year_in_title": f"{S['title_year']} з {S['analysed_ok']}", "words": S["title_words"], "brand": ctx["cfg"]["brand"],
                              "limits": {"title": T["title_max"], "description": T["description_max"]}, "description_symbols": S["description_symbols"]},
            "exact_limit": {"total": T["exact_limit"], "headings": T["exact_in_headings"], "faq": T["exact_in_faq"]},
            "topics": {tid: t for tid, t in tp.items() if t["competitors"] >= 2},
            "gaps": [tid for tid, t in tp.items() if t["gap"]],
            "competitor_faq_questions": {tz.host(c["url"]): c["faq"]["questions"][:8] for c in C["competitors"] if c.get("ok") and c["faq"]["questions"]},
            "term_candidates": [{"term": t["term"], "competitors": t["competitors"], "anchor_only": t["head_word_of_other_page"]} for t in E["terms"]],
            "own": {k: C["own"].get(k) for k in ("title", "description", "h1", "schema_types", "ui_messages")},
        },
        "doc_title": "", "header": [], "goal": [], "volume": {"range": [], "words": "", "why": []},
        "structure": [{"level": "H1", "heading": "", "chars": None, "topic": None, "note": ""}, {"level": "intro", "heading": "(без заголовка, одразу під H1)", "chars": [150, 250], "topic": None, "note": ""},
                      {"level": "listing", "heading": "(наявний блок пропозицій, без нового заголовка від копірайтера)", "chars": None, "topic": None, "note": ""},
                      {"level": "H2", "heading": "", "chars": [0, 0], "topic": None, "clusters": [], "note": ""}],
        "faq": [{"q": "", "note": ""}], "exact_text": [], "keywords": {k["keyword"]: {"place": "", "count": "", "block": "", "why": ""} for k in ctx["keys"]},
        "lists": [], "tables": [], "photos": [], "terms": {}, "terms_skip": [],
        "links": [{"page": n["page"], "anchors": ["", ""], "where": ""} for n in ctx["neighbours"]], "links_skip": {}, "links_extra": [],
        "bans": [], "competitors_better": [], "how_to_beat": [],
        "meta": {"A": {"title": {"text": "", "why": ""}, "description": {"text": "", "why": ""}, "h1": {"text": "", "why": ""}}, "tests": []},
        "developer": [], "subtopics_uk": {}, "gaps_declined": {},
    }


def main():
    ap = tz.args_page(argparse.ArgumentParser())
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    ctx = tz.load_ctx(a.workdir, a.page)
    C, E = load_data(ctx)
    if a.draft:
        tz.wjson(ctx["f"]["draft"], draft(ctx, C, E))
        print("чернетку записано:", ctx["f"]["draft"])
        return
    if not os.path.exists(ctx["f"]["plan"]):
        tz.die(f"немає {ctx['f']['plan']}. Зробіть чернетку (--draft), заповніть і збережіть під цим іменем.")
    plan = tz.rjson(ctx["f"]["plan"])
    err, warn = check(ctx, plan, C, E)
    heads, faq, text = exact_plan(ctx, plan)
    lo, hi = sums(plan)
    print(f"точні входження «{ctx['main']}»: заголовки {len(heads)}, FAQ {len(faq)}, текст {len(text)}, разом {len(heads) + len(faq) + len(text)} (ліміт {ctx['T']['exact_limit']})")
    print(f"сума обсягів блоків: {lo}–{hi}; діапазон: {plan['volume']['range']}")
    for w in warn:
        print("УВАГА:", w)
    for e in err:
        print("ПОМИЛКА:", e)
    print("план пройшов перевірку" if not err else f"помилок: {len(err)}")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
