#!/usr/bin/env python3
"""Owner decisions applied to keywords.json (idempotent, no API calls).

python scripts/apply_decisions.py
 - PAGE_OVERRIDES: Lara + last minute keywords go to the matrix page /tour/turkei/antalya/last-minute (field page_override).
 - MANUAL_FILTER : keyword is removed from the working list and moved to "filtered" with the given reason.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_OVERRIDES = {
    "last minute urlaub antalya lara": "/tour/turkei/antalya/last-minute",
    "last minute urlaub türkei lara": "/tour/turkei/antalya/last-minute",
    "last minute urlaub lara": "/tour/turkei/antalya/last-minute",
}
MANUAL_FILTER = {
    "günstig in die türkei fliegen": "запит про авіаквитки, не тур",
}


def main():
    p = os.path.join(ROOT, "keywords.json")
    d = json.load(open(p, encoding="utf-8"))
    for k in d["keywords"]:
        if k["keyword"] in PAGE_OVERRIDES:
            k["page_override"] = PAGE_OVERRIDES[k["keyword"]]
    moved = [k for k in d["keywords"] if k["keyword"] in MANUAL_FILTER]
    d["keywords"] = [k for k in d["keywords"] if k["keyword"] not in MANUAL_FILTER]
    for k in moved:
        d["filtered"].append({"keyword": k["keyword"], "reason": MANUAL_FILTER[k["keyword"]]})
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("overrides:", sum(1 for k in d["keywords"] if k.get("page_override")), "| moved to filtered:", [k["keyword"] for k in moved])


if __name__ == "__main__":
    main()
