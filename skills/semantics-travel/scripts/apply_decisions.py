#!/usr/bin/env python3
"""semantics-travel / apply_decisions: owner decisions saved in <workdir>/semantics-decisions.json (survive every recluster).

python apply_decisions.py [--workdir .] <command> ...
  show
  filter <keyword> <reason>                 move the keyword to "Відфільтровані" (also edits keywords.json)
  page-override <keyword> <page>            force a matrix/other page for a keyword (field page_override)
  override <keyword> <page> <reason>        keyword -> page "за рішенням власника" (wins over the SERP and business rules)
  verdict <page> <окрема|фільтр> <reason>   result of the check of a disputed (3-4 of 10) page type
  manual-check <keyword> <reason>           mark "перевірити вручну"
  note <page> <text>                        note for a page in "Розподіл по сторінках"
  known-position <keyword> <text>           known position of the site outside the TOP-10 (e.g. from Labs)
  region-page <region-slug> <page>          page of an extended region (extend_region/add_region)
  serp-check <keyword> <domain1> <domain2>  domains of the real TOP seen in a browser (to compare with the API)
  business-rule <name> <match-regex> <family> <page> [--exclude-region] [--exclude <regex>]... [--exception <keyword>]... [--note <text>]
  apply                                     write filter/page-override decisions into keywords.json (analyze does it in memory anyway)
No API calls.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--exclude-region", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--exception", action="append", default=[])
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    d = C.load_decisions(a.workdir)
    x = a.args
    if a.cmd == "show":
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    if a.cmd == "filter":
        d["manual_filter"][x[0]] = x[1]
    elif a.cmd == "page-override":
        d["page_overrides"][x[0]] = x[1]
    elif a.cmd == "override":
        d["keyword_overrides"][x[0]] = {"page": x[1], "reason": x[2]}
    elif a.cmd == "verdict":
        d["contested_verdicts"][x[0]] = {"verdict": x[1], "reason": x[2]}
    elif a.cmd == "manual-check":
        d["manual_check"][x[0]] = x[1]
    elif a.cmd == "note":
        d["page_notes"][x[0]] = x[1]
    elif a.cmd == "known-position":
        d["known_positions"][x[0]] = x[1]
    elif a.cmd == "region-page":
        d["region_pages"][x[0]] = x[1]
    elif a.cmd == "serp-check":
        d["serp_manual_check"] = {"keyword": x[0], "domains": x[1:]}
    elif a.cmd == "business-rule":
        d["business_rules"] = [r for r in d["business_rules"] if r.get("name") != x[0]]
        d["business_rules"].append({"name": x[0], "match": x[1], "family": x[2], "page": x[3], "exclude_region": a.exclude_region,
                                    "exclude_patterns": a.exclude, "exceptions": a.exception, "note": a.note})
    elif a.cmd == "apply":
        pass
    else:
        sys.exit("unknown command; see --help")
    C.save_decisions(a.workdir, d)
    kp = os.path.join(a.workdir, "keywords.json")
    if os.path.exists(kp):
        kw = json.load(open(kp, encoding="utf-8"))
        n0 = len(kw["keywords"])
        C.apply_decisions_to_keywords(kw, d)
        json.dump(kw, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"decisions saved; keywords.json: {n0} -> {len(kw['keywords'])} keywords, {len(kw['filtered'])} filtered")
    else:
        print("decisions saved")


if __name__ == "__main__":
    main()
