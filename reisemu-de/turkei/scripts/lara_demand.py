#!/usr/bin/env python3
"""Demand check for Lara (Antalya): Labs keyword suggestions + related keywords, then SERP for the top keywords.

python scripts/lara_demand.py [--max-cost 0.16] [--seeds "lara urlaub" "lara türkei"] [--related-seed "lara urlaub"] [--serp 3]

Germany (location_code 2276), de.  Raw responses -> lara-raw/.  Result -> lara-demand.json (no changes to semantics-turkei.xlsx).
Credentials: fetch_serp.load_auth() (never printed).  Stops before the cost cap is exceeded.
"""
import argparse, collections, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_serp as F
import analyze as A

ROOT = A.ROOT
RAW = os.path.join(ROOT, "lara-raw")
LABS = "https://api.dataforseo.com/v3/dataforseo_labs/google/"
GENERIC = set("lara türkei turkei antalya urlaub reise reisen hotel hotels hotelbewertung günstig günstige billig all inclusive inklusive 2026 2027 2025 sterne stern "
              "mit flug und in der die den für am strand familie familienurlaub kinder last minute pauschalreise pauschalreisen buchen angebote beach kurzurlaub "
              "wochen woche tage deutsch ab nach von bei zu im oder bewertung erfahrungen luxus spa wellness ultra premium 5 4 3 7 14 ai deluxe resort club".split())
TRANSLATIONS = {   # by meaning and search intent, own translation; Lara = курортний район Анталії
    "liberty lara türkei": "готель Liberty Lara у Лара (Туреччина)",
    "fame residence lara & spa türkei": "готель Fame Residence Lara & Spa у Лара (Туреччина)",
    "türkei lara wetter": "погода в Лара (Туреччина)",
    "lara türkei": "Лара (Туреччина): курорт, відпочинок",
    "grand park lara türkei": "готель Grand Park Lara у Лара (Туреччина)",
    "türkei lara miracle resort": "готель Miracle Resort у Лара (Туреччина)",
    "titanic beach lara resort antalya türkei": "готель Titanic Beach Lara Resort (Лара, Анталія, Туреччина)",
    "wetter lara türkei 30 tage": "погода в Лара (Туреччина) на 30 днів",
    "lara hotels": "готелі в Лара",
    "türkei hotel lara": "готелі в Лара (Туреччина)",
    "wetter lara türkei 16 tage": "погода в Лара (Туреччина) на 16 днів",
    "urlaub türkei lara": "відпочинок у Лара (Туреччина)",
    "türkei lara karte": "карта Лара (Туреччина)",
    "hotel royal wings türkei lara": "готель Royal Wings у Лара (Туреччина)",
    "wetter lara türkei 7 tage": "погода в Лара (Туреччина) на 7 днів",
    "wetter lara türkei 10-tage": "погода в Лара (Туреччина) на 10 днів",
    "hotel melas lara türkei": "готель Melas Lara у Лара (Туреччина)",
    "5 sterne hotels türkei lara": "5-зіркові готелі в Лара (Туреччина)",
    "lara urlaub": "відпочинок у Лара",
    "10 besten hotels in lara türkei": "10 найкращих готелів у Лара (Туреччина)",
}
INFO_TOKENS = {"wetter", "karte", "klima", "temperatur", "flughafen", "anreise", "entfernung", "webcam"}
ENTITY_NOISE = {"hotel", "hotels", "resort", "türkei", "turkei", "antalya", "lara", "spa", "beach", "residence", "palace"}
EXCLUDE = re.compile(r"croft|fabian|lara\.de|lara-|laranja|lara bingle|lara trump|lara stone|lara c|laura", re.I)


def post(auth, endpoint, body):
    req = urllib.request.Request(LABS + endpoint, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def items_of(resp, related=False):
    out = []
    task = resp["tasks"][0]
    for res in task.get("result") or []:
        for it in res.get("items") or []:
            kd = it["keyword_data"] if related else it
            ki = kd.get("keyword_info") or {}
            out.append({"keyword": kd["keyword"], "volume": ki.get("search_volume") or 0, "cpc": ki.get("cpc"),
                        "intent": (kd.get("search_intent_info") or {}).get("main_intent"),
                        "kd": (kd.get("keyword_properties") or {}).get("keyword_difficulty")})
    return out


def norm(k):
    t = k.lower().replace("-", " ").replace("''", " ").replace("'", " ")
    t = re.sub(r"all[ -]?inclusive|all[ -]?inklusiv|alles inklusive", "ai", t)
    toks = [x for x in t.split() if x not in ("in", "der", "die", "den", "am", "im", "und", "mit", "für")]
    toks = [{"reisen": "reise", "hotels": "hotel", "günstige": "günstig"}.get(x, x) for x in toks]
    return " ".join(sorted(toks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-cost", type=float, default=0.16)
    ap.add_argument("--seeds", nargs="+", default=["lara urlaub", "lara türkei"])
    ap.add_argument("--related-seed", default="lara urlaub")
    ap.add_argument("--serp", type=int, default=3)
    ap.add_argument("--serp-extra", nargs="*", default=[], help="additional keywords for SERP (e.g. the literal top-3 by volume)")
    ap.add_argument("--related-seeds", nargs="+", default=["lara urlaub", "lara türkei"])
    ap.add_argument("--spent-before", type=float, default=0.0, help="cost already spent in earlier runs (counts against --max-cost)")
    ap.add_argument("--no-reuse", action="store_true", help="call the API even if a raw file exists")
    a = ap.parse_args()
    auth = F.load_auth()
    os.makedirs(RAW, exist_ok=True)
    spent, cands = a.spent_before, []

    def guard(est):
        if spent + est > a.max_cost:
            sys.exit(f"cost cap: spent {spent:.4f} + next {est:.4f} > {a.max_cost}")

    base = {"location_code": 2276, "language_code": "de", "limit": 100,
            "filters": [["keyword_info.search_volume", ">=", 10]], "order_by": ["keyword_info.search_volume,desc"]}
    for seed in a.seeds:
        fn = os.path.join(RAW, f"suggestions-{re.sub(r'[^a-z0-9]+', '-', seed.lower())}.json")
        if os.path.exists(fn) and not a.no_reuse:
            resp = json.load(open(fn, encoding="utf-8"))          # already paid for: reuse
        else:
            guard(0.05)
            resp = post(auth, "keyword_suggestions/live", [dict(base, keyword=seed)])
            json.dump(resp, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            spent += float(resp.get("cost") or 0)
        got = items_of(resp)
        print(f"suggestions '{seed}': {len(got)} keywords, cost ${resp.get('cost')}")
        for g in got:
            g["source"] = f"suggestions:{seed}"
        cands += got
    rbase = {"location_code": 2276, "language_code": "de", "depth": 1, "limit": 60,
             "filters": [["keyword_data.keyword_info.search_volume", ">=", 10]], "order_by": ["keyword_data.keyword_info.search_volume,desc"]}
    for rs in a.related_seeds:
        fn = os.path.join(RAW, f"related-{re.sub(r'[^a-z0-9]+', '-', rs.lower())}.json")
        if os.path.exists(fn) and not a.no_reuse:
            resp = json.load(open(fn, encoding="utf-8"))
        else:
            guard(0.05)
            resp = post(auth, "related_keywords/live", [dict(rbase, keyword=rs)])
            json.dump(resp, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            spent += float(resp.get("cost") or 0)
        got = items_of(resp, related=True)
        print(f"related '{rs}': {len(got)} keywords, cost ${resp.get('cost')}, status {resp['tasks'][0].get('status_code')}")
        for g in got:
            g["source"] = f"related:{rs}"
        cands += got

    # keep Lara keywords, dedupe word-order variants
    best = {}
    for c in cands:
        kl = c["keyword"].lower()
        if not re.search(r"(?<![a-z])lara(?![a-z])", kl) or EXCLUDE.search(kl):
            continue
        key = norm(kl)
        if key not in best or c["volume"] > best[key]["volume"]:
            best[key] = dict(c, variants=[])
        if c["keyword"] != best[key]["keyword"]:
            best[key]["variants"].append(c["keyword"])
    rows = sorted(best.values(), key=lambda r: -r["volume"])
    for r in rows:
        toks = re.findall(r"\w+", r["keyword"].lower())
        extra = [t for t in toks if t not in GENERIC and not t.isdigit()]
        info = [t for t in toks if t in INFO_TOKENS]
        r["category"] = "інформаційний (погода/карта)" if info else ("назва готелю" if extra else "загальний")
        r["hotel_name"] = r["category"] == "назва готелю"
        r["entity"] = " ".join(sorted(t for t in extra if t not in ENTITY_NOISE)) if extra else ""
        r["extra_tokens"] = extra
    seen, ded = {}, []                      # same hotel written in different word orders -> one entity
    for r in rows:
        if r["category"] == "назва готелю" and r["entity"]:
            if r["entity"] in seen:
                seen[r["entity"]]["variants"].append(r["keyword"])
                continue
            seen[r["entity"]] = r
        ded.append(r)
    rows = ded
    print(f"Lara keywords after dedupe: {len(rows)}; spent so far ${spent:.4f}")

    # SERP for the top generic (not hotel-name) keywords
    top3 = [r for r in rows if r["category"] == "загальний"][: a.serp] + [r for r in rows if r["keyword"] in a.serp_extra]
    serp_out = {}
    sdir = os.path.join(RAW, "serp")
    os.makedirs(sdir, exist_ok=True)
    for r in top3:
        kw = r["keyword"]
        if not (os.path.exists(os.path.join(sdir, F.slug(kw) + ".json")) and not a.no_reuse):
            guard(0.002)
            kw, cost, err = F.fetch(kw, auth, sdir)
            if err:
                print("SERP error", kw, err)
                continue
            spent += cost
        d = json.load(open(os.path.join(sdir, F.slug(kw) + ".json"), encoding="utf-8"))
        res = d["response"]["tasks"][0]["result"][0]
        organic = [it for it in res["items"] if it["type"] == "organic"]
        rows_s = []
        for it in organic:
            typ, reg = A.classify_url(it["url"], it.get("title") or "")
            rows_s.append({"position": it["rank_group"], "url": it["url"], "domain": it["domain"], "title": it.get("title") or "",
                           "type": A.type_label(typ, reg), "region": reg})
        serp_out[kw] = {"check_url": res.get("check_url"), "datetime": res.get("datetime"), "results": rows_s}
    for r in rows:
        r["translation_uk"] = TRANSLATIONS.get(r["keyword"], "")
    out = {"seeds": a.seeds, "related_seed": a.related_seed, "cost_usd": round(spent, 4), "keywords": rows, "serp": serp_out}
    json.dump(out, open(os.path.join(ROOT, "lara-demand.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"TOTAL cost per API fields: ${spent:.4f}; wrote lara-demand.json")
    for r in rows[:30]:
        print(f"{r['volume']:>6} {r['category'][:12]:<12} {r['keyword']}  intent={r['intent']} cpc={r['cpc']} kd={r['kd']} src={r['source']}")
    for kw, v in serp_out.items():
        print("\n##", kw, v["check_url"])
        for x in v["results"]:
            print(f"  {x['position']:>2} {x['type']:<22} {x['domain']:<26} {x['url'][:80]}")


if __name__ == "__main__":
    main()
