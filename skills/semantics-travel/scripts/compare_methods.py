#!/usr/bin/env python3
"""semantics-travel / compare_methods: SERP-only clustering variants versus the lemma clusters (no API calls; reference only).

python compare_methods.py [--workdir .] [--out-dir .] [--serp-dir serp-raw-regular]
Needs clusters.json from analyze.py (in --out-dir).  Methods:
  A   soft-3, exact URLs (shared normalised URLs with the cluster head >= 3)
  B   domain + page type signature (sonnenklar.tv|hub != sonnenklar.tv|last-minute), threshold 4 (soft, hard) and 3 (soft, sensitivity)
Writes cluster-methods-comparison.md: cluster counts, precision/recall against the lemma clusters, and where the methods disagree.
In the first project the SERP-only methods gave 48-62 clusters for 78 keywords (91 % of pairs share no URL), which is why the lemma/intent
clusters stay the base and SERP overlaps are only a confirmation.
"""
import argparse, collections, itertools, json, os, sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A
import sp_common as C


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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--out-dir")
    ap.add_argument("--serp-dir", default="serp-raw-regular")
    a = ap.parse_args()
    S = C.load_settings(a.workdir, a.claude_md)
    R, _ = C.load_rules(S, a.workdir)
    out = a.out_dir or a.workdir
    _, _, K, serp = A.load_data(a.workdir, a.serp_dir)
    order = sorted(K, key=lambda k: -K[k]["volume"])
    U = {k: {C.nu(r["url"]) for r in serp[k]["results"]} for k in order}

    def sig(r):
        typ, _ = R.classify_url(r["url"], r["title"])
        d = C.reg_domain(urlsplit(r["url"]).netloc)
        return (d, typ) if typ != "other" else (d, "other:" + C.nu(r["url"]))

    SIG = {k: {sig(r) for r in serp[k]["results"]} for k in order}
    cl_json = json.load(open(os.path.join(out, "clusters.json"), encoding="utf-8"))["clusters"]
    lem = [[m for m in c["members"] if m in K] for c in cl_json]
    lem = [c for c in lem if c]
    lid = {k: c["id"] for c in cl_json for k in c["members"]}
    page_of = {k: c["page"] for c in cl_json for k in c["members"]}
    methods = collections.OrderedDict([("A  soft-3, точні URL", cluster(order, U, 3, False)), ("B1 домен+тип, поріг 4, soft", cluster(order, SIG, 4, False)),
                                       ("B2 домен+тип, поріг 4, hard", cluster(order, SIG, 4, True)), ("B3 домен+тип, поріг 3, soft", cluster(order, SIG, 3, False))])
    LP = pairs(lem)
    md = ["# Порівняння SERP-кластеризації з кластерами за лемою", "", f"Ключів: {len(order)}; кластерів за лемою: {len(lem)}.", "",
          "| Метод | кластерів | з 2+ ключами | пар разом | точність | повнота | кластерів, що зводять різні сторінки |", "|---|---|---|---|---|---|---|"]
    for name, cl in methods.items():
        P = pairs(cl)
        both = len(P & LP)
        multi = [c for c in cl if len(c) > 1]
        md.append(f"| {name} | {len(cl)} | {len(multi)} | {len(P)} | {both / len(P):.0%} | {both / len(LP):.0%} | {sum(1 for c in multi if len({page_of[k] for k in c}) > 1)} |"
                  if P and LP else f"| {name} | {len(cl)} | {len(multi)} | {len(P)} | – | – | – |")
    md += ["", "Точність = частка пар методу, що збігаються з лемою; повнота = частка пар за лемою, яких досяг метод.", ""]
    for name, cl in methods.items():
        md += [f"## {name}", "", "Кластери, що охоплюють кілька лем (кандидати на злиття/конфлікт):", ""]
        n = 0
        for c in sorted((c for c in cl if len(c) > 1), key=lambda c: -sum(K[k]["volume"] for k in c)):
            ids = sorted({lid[k] for k in c})
            if len(ids) > 1:
                n += 1
                md.append(f"- [{', '.join(ids)}] " + " ; ".join(f"{k} ({lid[k]})" for k in c))
        md += (["- немає"] if not n else []) + [""]
    open(os.path.join(out, "cluster-methods-comparison.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
