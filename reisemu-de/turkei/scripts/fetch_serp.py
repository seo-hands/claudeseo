#!/usr/bin/env python3
"""Fetch Google SERP TOP-10 for a keyword list straight from the DataForSEO API.

Reusable: python scripts/fetch_serp.py [--keywords keywords.json] [--out serp-raw]
                                      [--max-cost 0.20] [--force] [--only "kw1" "kw2"]

- Credentials: C:\\Users\\powde\\.config\\claude-seo\\dataforseo.env
  (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD). The values are never printed.
- Endpoint: /v3/serp/google/organic/live/regular (default, see the comment at ENDPOINT), one request per keyword.
- Params: location_code 2276 (Germany), language_code de, se_domain google.de,
  device desktop, depth 10.
- Every raw API response is saved as-is to <out>/<slug>.json; keywords that
  already have a raw file are skipped (no double paying) unless --force.
- Stops before exceeding --max-cost (USD), counted from the `cost` field in responses.
"""
import argparse, base64, hashlib, json, os, re, sys, time, unicodedata
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ENV_FILE = os.path.expanduser(r"~\.config\claude-seo\dataforseo.env")
URL = "https://api.dataforseo.com/v3/serp/google/organic/"
# Why live/regular and NOT live/advanced: in tests on 2026-10-07 (scripts/serp_variants.py, raw data in
# serp-variants/) live/advanced with location_code 2276 + se_domain google.de returned a SERP that did not
# match real google.de (browser check, German IP) -- 2 of 8 top domains for "türkei urlaub" -- although the
# response claimed se_domain=google.de. live/regular and the standard queue with the same parameters
# matched 8 of 8. location_name "Germany" without se_domain falls back to google.com and is wrong too.
# Same price (about $0.002 per live request).
ENDPOINT = "live/regular"
PARAMS = {"location_code": 2276, "language_code": "de", "se_domain": "google.de",
          "device": "desktop", "depth": 10}
EST_COST = 0.002  # per request, used only for the pre-flight guard


def load_auth():
    vals = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    login, pwd = vals.get("DATAFORSEO_LOGIN"), vals.get("DATAFORSEO_PASSWORD")
    if not login or not pwd:
        sys.exit("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not found in env file")
    return "Basic " + base64.b64encode(f"{login}:{pwd}".encode()).decode()


def slug(kw):
    a = unicodedata.normalize("NFKD", kw).encode("ascii", "ignore").decode()
    a = re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-")[:50]
    return f"{a}-{hashlib.sha1(kw.encode('utf-8')).hexdigest()[:8]}"


def fetch(kw, auth, out_dir, endpoint=None):
    body = json.dumps([dict(PARAMS, keyword=kw)]).encode("utf-8")
    req = urllib.request.Request(URL + (endpoint or ENDPOINT), data=body, method="POST",
                                 headers={"Authorization": auth, "Content-Type": "application/json"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read().decode("utf-8"))
            task = resp["tasks"][0]
            if resp.get("status_code") != 20000 or task.get("status_code") != 20000:
                return kw, None, f"API status {resp.get('status_code')}/{task.get('status_code')}: {task.get('status_message')}"
            with open(os.path.join(out_dir, slug(kw) + ".json"), "w", encoding="utf-8") as f:
                json.dump({"keyword": kw, "request": dict(PARAMS, keyword=kw), "endpoint": endpoint or ENDPOINT,
                           "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"), "response": resp},
                          f, ensure_ascii=False)
            return kw, float(resp.get("cost") or 0), None
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            time.sleep(2 * (attempt + 1))
    return kw, None, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default="keywords.json")
    ap.add_argument("--out", default="serp-raw")
    ap.add_argument("--max-cost", type=float, default=0.20)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--endpoint", default=ENDPOINT, help="live/regular (default; see comment above) or live/advanced")
    a = ap.parse_args()
    data = json.load(open(a.keywords, encoding="utf-8"))
    kws = [k["keyword"] if isinstance(k, dict) else k for k in data.get("keywords", data)]
    if a.only:
        kws = [k for k in kws if k in set(a.only)]
    os.makedirs(a.out, exist_ok=True)
    todo = [k for k in kws if a.force or not os.path.exists(os.path.join(a.out, slug(k) + ".json"))]
    print(f"keywords: {len(kws)}, to fetch: {len(todo)}, estimated cost: ${len(todo) * EST_COST:.3f}")
    if len(todo) * EST_COST > a.max_cost:
        sys.exit(f"estimated cost exceeds --max-cost {a.max_cost}")
    auth = load_auth()
    spent, errors = 0.0, []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for kw, cost, err in ex.map(lambda k: fetch(k, auth, a.out, a.endpoint), todo):
            if err:
                errors.append((kw, err))
            else:
                spent += cost
    print(f"fetched: {len(todo) - len(errors)}, errors: {len(errors)}, cost from API: ${spent:.4f}")
    for kw, err in errors:
        print("ERR", kw, "->", err)


if __name__ == "__main__":
    main()
