#!/usr/bin/env python3
"""Diagnostic: fetch the same keyword through different DataForSEO SERP endpoints/params and
compare with a reference TOP (domains seen in a real browser).  Raw responses -> serp-variants/.

python scripts/serp_variants.py [--budget 0.03] [--keywords "türkei urlaub" "pauschalreise türkei"]
Credentials come from fetch_serp.load_auth() (never printed).
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_serp as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "serp-variants")
API = "https://api.dataforseo.com/v3/serp/google/organic/"
REF_DOMAINS = {"türkei urlaub": ["schauinsland-reisen", "holidaycheck", "sonnenklar", "anextour", "coraltravel",
                                 "aldi-reisen", "restplatzboerse", "check24"]}
CODE = {"location_code": 2276, "language_code": "de", "se_domain": "google.de", "device": "desktop", "depth": 10}
NAME = {"location_name": "Germany", "language_code": "de", "device": "desktop", "depth": 10}


def call(auth, method, path, body=None):
    req = urllib.request.Request(API + path, method=method, headers={"Authorization": auth, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode("utf-8") if body is not None else None)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def organic(resp):
    task = resp["tasks"][0]
    res = (task.get("result") or [{}])[0]
    rows = [(it["rank_group"], it["domain"].replace("www.", ""), it["url"]) for it in res.get("items", []) if it["type"] == "organic"]
    return task, res, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.03)
    ap.add_argument("--keywords", nargs="+", default=["türkei urlaub", "pauschalreise türkei"])
    a = ap.parse_args()
    auth = F.load_auth()
    os.makedirs(OUT, exist_ok=True)
    plan = [("live/advanced", "live/advanced", CODE, 0.002),
            ("live/regular + location_code/se_domain", "live/regular", CODE, 0.002),
            ("live/regular + location_name Germany", "live/regular", NAME, 0.002),
            ("task_post(standard queue) + location_code/se_domain", "task_post", CODE, 0.0006),
            ("task_post(standard queue) + location_name Germany", "task_post", NAME, 0.0006)]
    skip_adv = os.environ.get("SKIP_LIVE_ADVANCED", "1") == "1"  # already covered by fetch_serp.py runs
    est = sum(c for n, e, p, c in plan if not (skip_adv and n == "live/advanced")) * len(a.keywords)
    print(f"estimated cost ${est:.4f} (budget ${a.budget})")
    if est > a.budget:
        sys.exit("over budget")
    spent, pending, results = 0.0, [], []
    for kw in a.keywords:
        for name, ep, params, _ in plan:
            if skip_adv and name == "live/advanced":
                continue
            body = [dict(params, keyword=kw)]
            if ep == "task_post":
                body[0]["priority"] = 1
            resp = call(auth, "POST", ep, body)
            task = resp["tasks"][0]
            spent += float(task.get("cost") or 0)
            tag = re.sub(r"[^a-z0-9]+", "-", f"{kw}-{name}".lower().replace("ü", "u")).strip("-")
            json.dump({"keyword": kw, "variant": name, "request": body, "response": resp}, open(os.path.join(OUT, tag + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            if ep == "task_post":
                pending.append((kw, name, task["id"], tag))
            else:
                results.append((kw, name, task["id"], resp, tag))
    for kw, name, tid, tag in pending:  # poll standard-queue tasks
        for _ in range(40):
            time.sleep(5)
            try:
                resp = call(auth, "GET", f"task_get/advanced/{tid}")
            except urllib.error.HTTPError as e:
                continue
            t = resp["tasks"][0]
            if t.get("status_code") == 20000 and t.get("result"):
                json.dump({"keyword": kw, "variant": name, "response": resp}, open(os.path.join(OUT, tag + "-get.json"), "w", encoding="utf-8"), ensure_ascii=False)
                results.append((kw, name, tid, resp, tag))
                break
        else:
            print("task not ready:", kw, name, tid)
    print(f"cost per API fields: ${spent:.4f}")
    for kw, name, tid, resp, tag in results:
        task, res, rows = organic(resp)
        ref = REF_DOMAINS.get(kw)
        hit = sum(1 for _, d, _ in rows if ref and any(r in d for r in ref)) if ref else None
        print(f"\n## {kw} | {name} | task_id={tid} | se_domain={res.get('se_domain')} | datetime={res.get('datetime')} | organic={len(rows)}"
              + (f" | збігів із реальним ТОП (домени): {hit}/{len(ref)}" if ref else ""))
        print("   check_url:", res.get("check_url"))
        for pos, d, u in rows:
            print(f"   {pos:>2} {d:<28} {u[:80]}")


if __name__ == "__main__":
    main()
