#!/usr/bin/env python3
"""Compare SERP clustering variants with the lemma/intent clusters (no API calls).

python scripts/compare_methods.py [--serp-dir serp-raw-regular]

Methods
  A  soft-3 by exact URL (shared normalised URLs with the cluster head >= 3)
  B  domain+page-type signature: a result is (registrable domain, page type), e.g.
     sonnenklar.tv|hub vs sonnenklar.tv|last-minute are different; threshold 4 of 10.
     B-soft = shared signatures with the head >= 4, B-hard = with every member >= 4.
Output: cluster-methods-comparison.md  (lemma clusters in clusters.json are not modified)
"""
import argparse, collections, itertools, json, os, re, sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A

ROOT = A.ROOT
TYPES = [  # first match wins
    ("last-minute", r"last-?minute"),
    ("pauschalreise", r"pauschal"),
    ("all-inclusive", r"all-?inclusive|allinclusive"),
    ("rundreise", r"rundreise"),
    ("hotel", r"/(hotel|hotels|hi|hrd|hotelbewertung)/|-hotel-|/hotel-"),
    ("info", r"warnung|sicherheit|einreise|reisehinweis|reisetipps|reisezeit|wetter|klima|forum|blog|magazin|ratgeber|/faq|reisebericht|inspiration|visum|personalausweis|reisepass"),
    ("thema", r"familie|paare|romantik|staedtereise|fruehbucher|frühbucher|golf|wellness|kreuzfahrt|kinder|senioren|single|seniorenreisen|angebote"),
    ("region", r"side|antalya|alanya|belek|kemer|bodrum|marmaris|istanbul|kappadokien|cappadocia|riviera|aegaeis|ägäis|lara|fethiye|dalaman|didim|izmir|kusadasi|schwarzmeer|manavgat|avsallar|konakli"),
]
HUB = re.compile(r"/(urlaub|reisen|reiseziele|urlaubsziele|badereisen|reiseland|laender|europa|land)(/[a-z0-9-]+)*/(tuerkei|turkei|tuerkei-co4)(\.html|\.php)?/?$|/(tuerkei|turkei)(\.html|\.php)?/?$")


def reg_domain(host):
    host = host.lower().split(":")[0]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def page_type(url, title=""):
    u = urlsplit(url)
    path = u.path.lower()
    for name, pat in TYPES[:4]:
        if re.search(pat, path):
            return name
    if HUB.search(path):
        return "hub"
    for name, pat in TYPES[4:]:
        if re.search(pat, path):
            return name
    return "other"


def signature(r):
    u = r["url"]
    t = page_type(u, r["title"])
    d = reg_domain(urlsplit(u).netloc)
    return (d, t) if t != "other" else (d, "other:" + A.nu(u))


def cluster(order, S, thr, hard):
    cl = []
    for k in order:
        best, bs = None, -1
        for c in cl:
            if hard:
                ov = [len(S[k] & S[m]) for m in c]
                ok, sc = min(ov) >= thr, sum(ov) / len(ov)
            else:
                n = len(S[k] & S[c[0]])
                ok, sc = n >= thr, n
            if ok and sc > bs:
                best, bs = c, sc
        if best is None:
            cl.append([k])
        else:
            best.append(k)
    return cl


def pairs(cl):
    return {frozenset(p) for c in cl for p in itertools.combinations(c, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serp-dir", default="serp-raw-regular")
    a = ap.parse_args()
    cands, K, serp = A.load(ROOT, a.serp_dir)
    order = sorted(K, key=lambda k: -K[k]["volume"])
    lemma = json.load(open(os.path.join(ROOT, "clusters.json"), encoding="utf-8"))["lemma"]
    lid = {k: c["id"] for c in lemma for k in c["members"]}
    lcl = [c["members"] for c in lemma]
    page_of = {k: c["page"] for c in lemma for k in c["members"]}
    U = {k: {A.nu(r["url"]) for r in v["results"]} for k, v in serp.items()}
    SIG = {k: {signature(r) for r in v["results"]} for k, v in serp.items()}
    methods = collections.OrderedDict([
        ("A  soft-3, точні URL (з головним)", cluster(order, U, 3, False)),
        ("B1 домен+тип, поріг 4, soft (з головним)", cluster(order, SIG, 4, False)),
        ("B2 домен+тип, поріг 4, hard (з кожним)", cluster(order, SIG, 4, True)),
        ("B3 домен+тип, поріг 3, soft (чутливість)", cluster(order, SIG, 3, False)),
    ])
    LP = pairs(lcl)
    out = ["# Порівняння SERP-кластеризації з кластерами за лемою", "",
           f"Дані: {a.serp_dir} (live/regular, google.de, 78 ключів), без нових запитів до API. Кластери за лемою: {len(lcl)} (не змінювалися).", "",
           "Типи сторінок для методу B: last-minute, pauschalreise, all-inclusive, rundreise, hotel, info, thema, region, hub (хаб країни), other (унікальний URL). "
           "Підпис результату = (домен, тип), наприклад sonnenklar.tv|hub ≠ sonnenklar.tv|last-minute.", "",
           "## Підсумок", "",
           "| Метод | кластерів | з 2+ ключами | ключів у групах | пар разом | точність відносно лем | повнота відносно лем | кластерів, що зводять різні сторінки |", "|---|---|---|---|---|---|---|---|"]
    stats = {}
    for name, cl in methods.items():
        P = pairs(cl)
        both = len(P & LP)
        prec = both / len(P) if P else float("nan")
        rec = both / len(LP) if LP else float("nan")
        multi = [c for c in cl if len(c) > 1]
        xpage = sum(1 for c in multi if len({page_of[k] for k in c}) > 1)
        out.append(f"| {name} | {len(cl)} | {len(multi)} | {sum(len(c) for c in multi)} | {len(P)} | {prec:.0%} | {rec:.0%} | {xpage} |")
        stats[name] = (prec, rec)
    out += ["| **Лема/інтент** | **%d** | %d | %d | %d | – | – | 0 |" % (len(lcl), sum(1 for c in lcl if len(c) > 1), sum(len(c) for c in lcl if len(c) > 1), len(LP)), "",
            "«Кластерів, що зводять різні сторінки» — кластери методу, ключі яких за розподілом лем ведуть на різні сторінки (реальні конфлікти з розподілом). Точність = частка пар ключів, які метод об'єднав і які теж в одному кластері за лемою. Повнота = частка пар за лемою, які метод теж об'єднав.", ""]
    # type distribution of results
    tc = collections.Counter(page_type(r["url"], r["title"]) for v in serp.values() for r in v["results"])
    out += ["Розподіл типів сторінок у видачі: " + ", ".join(f"{t} {n}" for t, n in tc.most_common()), ""]
    for name, cl in methods.items():
        out += [f"## {name}", ""]
        multi = sorted((c for c in cl if len(c) > 1), key=lambda c: -sum(K[k]["volume"] for k in c))
        out.append(f"Кластерів {len(cl)}, із них 2+ ключів: {len(multi)}.")
        out.append("")
        out.append("**Де метод розходиться з лемами: кластер охоплює кілька лем (кандидати на злиття)**")
        out.append("")
        n_cross = 0
        for c in multi:
            ids = sorted({lid[k] for k in c})
            if len(ids) > 1:
                n_cross += 1
                out.append(f"- [{', '.join(ids)}] " + " ; ".join(f"{k} ({lid[k]})" for k in sorted(c, key=lambda x: -K[x]["volume"])))
        if not n_cross:
            out.append("- немає")
        out += ["", "**Кластери, що збігаються з однією лемою (2+ ключів)**", ""]
        same = [c for c in multi if len({lid[k] for k in c}) == 1]
        for c in same:
            out.append(f"- {lid[c[0]]}: " + " ; ".join(sorted(c, key=lambda x: -K[x]["volume"])))
        if not same:
            out.append("- немає")
        out += ["", "**Леми, які метод розкидає по різних кластерах**", ""]
        where = {k: i for i, c in enumerate(cl) for k in c}
        for lc in lemma:
            m = lc["members"]
            if len(m) < 2:
                continue
            groups = collections.Counter(where[k] for k in m)
            together = max(groups.values())
            out.append(f"- {lc['id']} ({lc['name'][:40]}): {len(m)} ключів у {len(groups)} кластерах методу, найбільша спільна група {together}")
        out.append("")
    open(os.path.join(ROOT, "cluster-methods-comparison.md"), "w", encoding="utf-8").write("\n".join(out))
    print("\n".join(out[:16]))
    print("written cluster-methods-comparison.md,", len(out), "lines")


if __name__ == "__main__":
    main()
