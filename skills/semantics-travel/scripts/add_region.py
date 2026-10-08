#!/usr/bin/env python3
"""semantics-travel / add_region: put reviewed region keywords into keywords.json (no API calls).

python add_region.py --region <name> --classification classification.json [--page /section/country/region/<name>] [--workdir .]

classification.json (made by Claude after reviewing region-<slug>-demand.json and agreeing with the owner):
  {"keyword": {"group": "general | hotels_list | hotel_name | filter",
               "translation": "переклад українською", "note": "примітка (необов'язково)",
               "reason": "для filter: причина", "page_override": "матриця (необов'язково)"}, ...}
 general / hotels_list -> page of the region (their keywords count into its volume); hotel_name -> sheet "Готелі <Region>"
 (single-hotel pages); filter -> "Відфільтровані" with the reason (weather/map/video/social services in the TOP, competitor brands, stale years ...).
Keywords already in the main list are not duplicated.  Every keyword of the demand file must be classified.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--region", required=True)
    ap.add_argument("--classification", required=True)
    ap.add_argument("--page", help="landing page of the region, e.g. /tour/<country>/<area>/<region> (saved in the decisions file)")
    a = ap.parse_args()
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", a.region.lower()).strip("-")
    dem = json.load(open(os.path.join(a.workdir, f"region-{slug}-demand.json"), encoding="utf-8"))
    cls = json.load(open(a.classification, encoding="utf-8"))
    missing = [r["keyword"] for r in dem["keywords"] if r["keyword"] not in cls]
    if missing:
        sys.exit(f"{len(missing)} ключів не класифіковано: {missing[:8]} ...")
    kp = os.path.join(a.workdir, "keywords.json")
    kw = json.load(open(kp, encoding="utf-8"))
    have = {k["keyword"] for k in kw["keywords"]}
    added = filt = 0
    for r in dem["keywords"]:
        k, c = r["keyword"], cls[r["keyword"]]
        if c["group"] == "filter":
            if not any(f["keyword"] == k for f in kw["filtered"]):
                kw["filtered"].append({"keyword": k, "reason": c.get("reason", "відфільтровано")})
                filt += 1
        elif k not in have:
            rec = {"keyword": k, "volume": r["volume"], "cpc": r.get("cpc"), "intent": r.get("intent"), "kd": r.get("kd"), "source": f"region:{slug}",
                   "ext_group": c["group"], "translation_uk": c.get("translation", ""), "translation_note_uk": c.get("note", "")}
            if c.get("page_override"):
                rec["page_override"] = c["page_override"]
            kw["keywords"].append(rec)
            added += 1
    json.dump(kw, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.page:
        d = C.load_decisions(a.workdir)
        d["region_pages"][slug] = a.page
        C.save_decisions(a.workdir, d)
    print(f"додано {added} ключів регіону «{a.region}», відфільтровано {filt}. Далі: analyze.py")


if __name__ == "__main__":
    main()
