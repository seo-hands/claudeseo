#!/usr/bin/env python3
"""semantics-travel / fetch_serp: Google SERP TOP-10 for every working keyword, straight from the DataForSEO API (no MCP, no agents).

python fetch_serp.py [--workdir .] [--keywords keywords.json] [--cache serp-raw-regular] [--only "kw1" "kw2"] [--yes]

Without --yes it only prints the cost estimate (nothing is requested).  Raw responses are cached one file per keyword;
a keyword already in the cache is never requested again.  Cost is tracked from the API `cost` fields and the run stops when
it exceeds the estimate by more than 30 %.

WHY live/regular + location_code + se_domain (do not change):
  * /serp/google/organic/live/advanced returned a SERP that did not match real google.de (browser check with a German IP:
    2 of 8 top domains) although the response claimed se_domain=google.de.  live/regular and the standard queue with the same
    parameters matched 8 of 8.
  * location_name without se_domain falls back to google.com and returns a wrong SERP.
  Price is the same (about $0.002 per keyword).
"""
import argparse, json, os, sys, time, urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C

ENDPOINT = "serp/google/organic/live/regular"


def request_params(S, kw):
    return {"keyword": kw, "location_code": S.location_code, "language_code": S.language, "se_domain": S.se_domain, "device": "desktop", "depth": 10}


def fetch_one(S, auth, kw, cache):
    params = request_params(S, kw)
    last = None
    for attempt in range(3):
        try:
            resp = C.api(auth, ENDPOINT, [params])
            task = resp["tasks"][0]
            if resp.get("status_code") != 20000 or task.get("status_code") != 20000:
                return kw, None, f"API {resp.get('status_code')}/{task.get('status_code')}: {task.get('status_message')}"
            with open(os.path.join(cache, C.slug_file(kw) + ".json"), "w", encoding="utf-8") as f:
                json.dump({"keyword": kw, "request": params, "endpoint": ENDPOINT, "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"), "response": resp}, f, ensure_ascii=False)
            return kw, float(resp.get("cost") or 0), None
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            time.sleep(2 * (attempt + 1))
    return kw, None, last


def working_keywords(workdir, keywords_file, only=None):
    kw = json.load(open(os.path.join(workdir, keywords_file), encoding="utf-8"))
    C.apply_decisions_to_keywords(kw, C.load_decisions(workdir))
    names = [k["keyword"] for k in kw["keywords"] if not k.get("source", "").startswith("region:")]
    return [k for k in names if k in set(only)] if only else names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--keywords", default="keywords.json")
    ap.add_argument("--cache", default="serp-raw-regular")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--yes", action="store_true", help="run the paid requests (after the estimate was confirmed by the user)")
    a = ap.parse_args()
    try:
        S = C.load_settings(a.workdir, a.claude_md)
    except C.ConfigMissing as e:
        sys.exit(C.config_help(e))
    cache = a.cache if os.path.isabs(a.cache) else os.path.join(a.workdir, a.cache)
    os.makedirs(cache, exist_ok=True)
    kws = working_keywords(a.workdir, a.keywords, a.only)
    todo = [k for k in kws if not os.path.exists(os.path.join(cache, C.slug_file(k) + ".json"))]
    print(f"ключів: {len(kws)}, у кеші: {len(kws) - len(todo)}, до запиту: {len(todo)}")
    est = C.print_estimate([("SERP live/regular (location_code + se_domain)", len(todo), C.PRICES["serp_live_regular"])])
    if not todo:
        print("Нічого запитувати.")
    elif not a.yes:
        print("Запити НЕ виконано. Покажіть оцінку користувачу, дочекайтесь підтвердження і запустіть з --yes.")
        return
    else:
        auth = C.load_auth()
        guard = C.CostGuard(est)
        errors = []
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for kw, cost, err in ex.map(lambda k: fetch_one(S, auth, k, cache), todo):
                if err:
                    errors.append((kw, err))
                else:
                    guard.add(cost)
        print(f"виконано: {len(todo) - len(errors)}, помилок: {len(errors)}, витрати за даними API: {guard}")
        for kw, err in errors:
            print("ПОМИЛКА", kw, "->", err)
    main_kw = S.get("main_keyword") or (kws[0] if kws else None)
    if main_kw:
        fn = os.path.join(cache, C.slug_file(main_kw) + ".json")
        if os.path.exists(fn):
            d = json.load(open(fn, encoding="utf-8"))
            res = d["response"]["tasks"][0]["result"][0]
            org = [f"{it['rank_group']}. {it['domain']}" for it in res["items"] if it["type"] == "organic"]
            line = f"check_url головного ключа «{main_kw}»: {res.get('check_url')} (API datetime {res.get('datetime')})"
            print("\n" + line + "\nТОП з API:", "; ".join(org))
            print("ЗВІРТЕ видачу вручну в браузері (режим інкогніто, локація/IP країни сайту) і повідомте, чи збігається.")
            open(os.path.join(a.workdir, "serp-check.txt"), "w", encoding="utf-8").write(line + "\n" + "\n".join(org) + "\n")


if __name__ == "__main__":
    main()
