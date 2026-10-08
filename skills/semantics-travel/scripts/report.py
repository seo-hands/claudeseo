#!/usr/bin/env python3
"""semantics-travel / report: DRAFT of recommendations-<slug>.md from analyze.py outputs (no API calls).

python report.py [--workdir .] [--out-dir .] [--force]
Writes recommendations-<slug>.draft.md (or recommendations-<slug>.md when --force).  The tables are exact; the numbered recommendations
(5-7 items for the page: what to change in title/H1, which sections to add, which pages to split/merge, cannibalization, priorities)
are written by Claude on top of the draft, in Ukrainian, with numbers taken from these tables.
"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C


def fmt(n):
    return f"{n:,}".replace(",", " ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--out-dir")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    S = C.load_settings(a.workdir, a.claude_md)
    out = a.out_dir or a.workdir
    cj = json.load(open(os.path.join(out, "clusters.json"), encoding="utf-8"))
    kw = json.load(open(os.path.join(a.workdir, "keywords.json"), encoding="utf-8"))
    ek = {k["keyword"] for k in kw["keywords"] if k.get("source", "").startswith("region:")}
    H, dec = cj["clusters"], cj["decisions"]
    K = {k["keyword"]: k for k in kw["keywords"]}
    pages = collections.OrderedDict()
    for c in sorted(H, key=lambda c: -c["total"]):
        pages.setdefault(c["page"], []).append(c)
    exist = set(S.existing_pages)
    L = [f"# Рекомендації для {S.site}{S.page_base}", "",
         f"Чернетка зі скіла semantics-travel. Країна/тема: {S.country}; ринок {S.language}, location_code {S.location_code}, {S.se_domain}. "
         f"Ключів у роботі {sum(len(c['members']) for c in H)}, сумарна частотність {fmt(sum(c['total'] for c in H))}.", "",
         "## Розподіл по сторінках", "", "| Сторінка | Стан | Кластери | Частотність |", "|---|---|---|---|"]
    for p, cs in pages.items():
        L.append(f"| {p} | {'існує' if p in exist else 'нова'} | {', '.join(c['id'] for c in cs)} | {fmt(sum(c['total'] for c in cs))} |")
    for title, status in (("Ключі «за бізнес-правилом»", "за бізнес-правилом"), ("Ключі «за рішенням власника»", "за рішенням власника"),
                          ("Ключі «перевірити вручну»", "перевірити вручну"), ("Спірні без перевірки (3–4 з 10)", "спірно (не перевірено)")):
        rows = [(k, d) for k, d in dec.items() if d["status"] == status and k in K and k not in ek]       # region-extension keywords are summarised below
        if rows:
            L += ["", f"## {title} ({len(rows)})", "", "| Ключ | Частотність | Сторінка |", "|---|---|---|"]
            L += [f"| {k} | {K[k]['volume']} | {d['page']} |" for k, d in sorted(rows, key=lambda x: -K[x[0]]["volume"])]
    regs = collections.defaultdict(list)
    for k in kw["keywords"]:
        if k.get("source", "").startswith("region:"):
            regs[k["source"].split(":", 1)[1]].append(k)
    for slug, ks in regs.items():
        hn = [k for k in ks if k.get("ext_group") == "hotel_name"]
        L += ["", f"## Район «{slug}» (ключі розширення)", "",
              f"- на сторінці району: {len(ks) - len(hn)} ключів, {fmt(sum(k['volume'] for k in ks if k not in hn))} запитів;",
              f"- назви готелів (окремий аркуш, сторінки окремих готелів): {len(hn)} ключів, {fmt(sum(k['volume'] for k in hn))} запитів."]
    fr = collections.Counter(f["reason"].split(" (")[0] for f in kw.get("filtered", []))
    L += ["", "## Відфільтровані", "", *(f"- {r}: {n}" for r, n in fr.most_common())]
    vf = os.path.join(a.workdir, "landing-verification.json")
    if os.path.exists(vf):
        L += ["", "## Перевірка спірних (render_page.py)", ""]
        for x in json.load(open(vf, encoding="utf-8")):
            L.append(f"- {x['id']}: збіг тексту {x['text_overlap_6gram']}; H1 «{'; '.join(x['a'].get('h1') or [])}» / «{'; '.join(x['b'].get('h1') or [])}»; "
                     f"власний текст {x['a'].get('own_text_words')} / {x['b'].get('own_text_words')} слів")
    L += ["", "## Рекомендації", "", "_Заповнює Claude: 5–7 пунктів для сторінки з числами з таблиць вище._", "",
          "## Обмеження", "", "- Видачу звірено вручну лише для головного ключа; для решти вона може відрізнятись.",
          "- SERP-кластеризація (hard-4/soft-3) — лише довідка; основа — лема й інтент.", f"- Частотність і CPC — DataForSEO Labs ({S.se_domain})."]
    fn = os.path.join(out, f"recommendations-{S.slug}" + ("" if a.force else ".draft") + ".md")
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("записано", fn)


if __name__ == "__main__":
    main()
