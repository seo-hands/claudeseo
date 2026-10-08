#!/usr/bin/env python3
"""Stage 2: on-page analysis of TOP competitor hubs and of the own hub page.

python scripts/analyze_competitors.py [--refresh]

Pages are rendered with the plugin's render_page.py (free, no DataForSEO); rendered HTML is cached in
competitors-raw/ so that re-analysis does not refetch.  Output: competitors-turkei.json.
Page content is untrusted data: it is parsed, never executed.
"""
import argparse, glob, hashlib, json, os, re, shutil, statistics, subprocess, sys
from urllib.parse import urljoin, urlparse

import openpyxl
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.expanduser(r"~\.claude\plugins\cache\agricidaniel-claude-seo\claude-seo\2.4.2\scripts\claude-seo")
RAW = os.path.join(ROOT, "competitors-raw")
OUT = os.path.join(ROOT, "competitors-turkei.json")
OWN = "https://reisemu.de/tour/turkei"
MAIN_KW = "türkei urlaub"
ADJACENT = ["urlaub türkei buchen", "türkei urlaub 2026", "türkei urlaub 2026 all inclusive mit flug und hotel", "türkei urlaub günstiger"]
COMPETITORS = [
    "https://www.schauinsland-reisen.de/urlaubsziele/tuerkei/tuerkische-riviera",
    "https://www.holidaycheck.de/urlaub/tuerkei",
    "https://www.sonnenklar.tv/urlaub/tuerkei.html",
    "https://www.anextour.de/urlaub/tuerkei/",
    "https://www.aldi-reisen.de/badereisen/tuerkei",
    "https://www.restplatzboerse.com/urlaub/tuerkei/",
    "https://urlaub.check24.de/urlaub/land/tuerkei-co4",
    "https://www.12-travel.de/reiseziele/T%C3%BCrkei/",
    "https://www.holidayplatz.de/urlaub/tuerkei",
    "https://www.oeger.de/urlaub/tuerkei/",
    "https://www.travelantis.de/ferienreisen-tuerkei.html",
    "https://www.lidl-reisen.de/urlaub/tuerkei",
]
# reserves were approved for holidaycheck/restplatzboerse; any other page that cannot be read (e.g. consent wall) takes the next free one
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
VENV_PY = os.path.join(os.environ.get("LOCALAPPDATA", ""), "claude-seo", ".venv", "Scripts", "python.exe")
OWN_SNIPPET = ("import sys, json; sys.path.insert(0, sys.argv[1]); from render_page import render_page; "
               "sys.stdout.reconfigure(encoding='utf-8'); "
               "print(json.dumps(render_page(sys.argv[2], mode='always', timeout_ms=45000, user_agent=sys.argv[3]), default=str))")
RESERVES = ["https://www.neckermann-reisen.de/urlaub/tuerkei/", "https://www.loveholidays.com/de/urlaub/tuerkei/"]
NOTES = {"https://www.schauinsland-reisen.de/urlaubsziele/tuerkei/tuerkische-riviera": "сторінка регіону (Türkische Riviera), а не країни"}

REGIONS = ["Antalya", "Side", "Alanya", "Belek", "Kemer", "Lara", "Bodrum", "Marmaris", "Fethiye", "Dalaman", "Izmir", "Kusadasi",
           "Didim", "Cesme", "Istanbul", "Kappadokien", "Pamukkale", "Ephesus", "Ölüdeniz", "Dalyan", "Türkische Riviera",
           "Türkische Ägäis", "Lykische Küste", "Schwarzmeer"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
SEASON_RE = re.compile(r"reisezeit|klima|wetter|temperatur|saison|jahreszeit|wann .*(reise|urlaub|türkei)|" + "|".join(m.lower() for m in MONTHS))
FAQ_RE = re.compile(r"\bfaq\b|häufig|fragen", re.I)
CTA_RE = re.compile(r"buchen|angebot|jetzt|suchen|finden|anzeigen|entdecken|ansehen|vergleichen|sichern|zum hotel|zur reise|mehr erfahren", re.I)
PRICE_RE = re.compile(r"(?:ab\s*)?(?:\d{1,3}(?:\.\d{3})+|\d{2,5})(?:,\d{1,2})?(?:,-)?\s?(?:€|eur\b)|(?:ab\s*)?€\s?(?:\d{1,3}(?:\.\d{3})+|\d{2,5})", re.I)
REVIEW_RE = re.compile(r"bewertung|weiterempfehlung|trustpilot|trusted shops|rezension|erfahrungsbericht|holidaycheck award", re.I)
SEARCH_RE = re.compile(r"reisezeitraum|abflughafen|reisedauer|reisende|wohin|hin- und rückreise|anreise|verpflegung|hotelkategorie", re.I)
BOILER = re.compile(r"cookie|consent|onetrust|usercentrics|newsletter|breadcrumb|navigation|navbar|nav-|-nav|menu|footer|header|modal|overlay|offcanvas|skip", re.I)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ").replace("\u00ad", "")).strip()


def nospace(s):
    return len(re.sub(r"\s+", "", s or ""))


def render(url, mode, refresh=False, own=False):
    os.makedirs(RAW, exist_ok=True)
    cache = os.path.join(RAW, re.sub(r"\W+", "_", urlparse(url).netloc + urlparse(url).path)[:70] + "_" + hashlib.md5((url + mode).encode()).hexdigest()[:6] + ".json")
    if os.path.exists(cache) and not refresh:
        return json.load(open(cache, encoding="utf-8"))
    bash = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"   # claude-seo launcher is a shell script
    cmd = [bash, RENDER.replace("\\", "/"), "run", "render_page.py", "--json", "--mode", mode, "--timeout-ms", "45000", url]
    if own:
        # own site answers 403 to the plugin's "ClaudeSEO/2.0" user agent (plain requests get 200), so the same
        # render_page() is called with a regular browser UA. Used ONLY for the owner's page, never for competitors.
        cmd = [VENV_PY, "-c", OWN_SNIPPET, os.path.dirname(RENDER), url, BROWSER_UA]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=240)
        txt = (r.stdout or b"").decode("utf-8", "replace")
        d = json.loads(txt[txt.index("{"):])
    except Exception as e:  # reported, not hidden
        d = {"url": url, "error": f"render failed: {type(e).__name__}: {str(e)[:200]}", "content": None}
    d.pop("raw_content", None)
    d.pop("accessibility_tree", None)
    json.dump(d, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return d


def is_boiler(el):
    for p in [el] + list(el.parents):
        if p.name in ("nav", "header", "footer", "aside", "form"):
            return True
        attrs = " ".join([p.get("id") or ""] + (p.get("class") or []) + [p.get("role") or ""]) if hasattr(p, "get") else ""
        if attrs and p.name not in ("body", "html", "main") and BOILER.search(attrs):
            return True
    return False


def jsonld(soup):
    types, faq_q, rating = set(), [], None
    for s in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        stack = [data]
        while stack:
            v = stack.pop()
            if isinstance(v, dict):
                t = v.get("@type")
                for x in (t if isinstance(t, list) else [t]):
                    if isinstance(x, str):
                        types.add(x)
                if v.get("@type") == "Question" and v.get("name"):
                    faq_q.append(norm(str(v["name"])))
                if v.get("@type") == "AggregateRating":
                    rating = {k: v.get(k) for k in ("ratingValue", "reviewCount", "ratingCount", "bestRating") if v.get(k) is not None}
                stack.extend(v.values())
            elif isinstance(v, list):
                stack.extend(v)
    return sorted(types), faq_q, rating


def kw_presence(kw, zones):
    """exact phrase count per zone + whether all words of the key occur in one sentence of the main text"""
    k = kw.lower()
    res = {z: len(re.findall(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t.lower())) for z, t in zones.items()}
    toks = [t for t in re.findall(r"\w+", k) if t not in ("im", "in", "mit", "und", "der", "die")]
    sents = re.split(r"(?<=[.!?])\s+|\n+", zones["text"].lower())
    res["all_words_in_sentence"] = sum(1 for s in sents if all(re.search(r"(?<!\w)" + re.escape(t), s) for t in toks))
    return res


def analyse(url, keywords, refresh=False):
    attempts = []
    d = None
    for mode in ("always", "auto"):
        d = render(url, mode, refresh, own=(url == OWN and mode == "always"))
        html = d.get("content") or ""
        ok = not d.get("error") and (d.get("status_code") or 0) < 400 and len(html) > 5000
        attempts.append({"mode": mode, "status": d.get("status_code"), "error": d.get("error"), "html_len": len(html), "mode_used": d.get("mode_used")})
        if ok:
            break
    res = {"url": url, "final_url": d.get("url"), "status": d.get("status_code"), "mode_used": d.get("mode_used"), "attempts": attempts,
           "error": d.get("error"), "ok": False}
    html = d.get("content") or ""
    if not html:
        return res
    soup = BeautifulSoup(html, "html.parser")
    types, faq_ld, rating = jsonld(soup)
    title = norm(soup.title.get_text()) if soup.title else ""
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    desc = norm(md.get("content")) if md else ""
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    body = soup.body or soup
    full_text = norm(body.get_text(" "))
    h1 = [norm(h.get_text(" ")) for h in body.find_all("h1") if norm(h.get_text(" "))]
    outline = [{"level": h.name, "text": norm(h.get_text(" "))[:200]} for h in body.find_all(["h2", "h3"])
               if norm(h.get_text(" ")) and not is_boiler(h)]

    # main text: block-level text units outside navigation/boilerplate; cards with short strings are dropped
    blocks, seen = [], set()
    for el in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "dd", "dt", "blockquote", "summary", "div", "span"]):
        if el.name in ("div", "span"):
            t = norm(" ".join(c for c in el.find_all(string=True, recursive=False)))
            if len(t) < 80:
                continue
        else:
            if el.name in ("li", "td", "dd") and el.find(["p", "li", "h2", "h3", "h4"]):
                continue
            t = norm(el.get_text(" "))
            minlen = 1 if el.name in ("h1", "h2", "h3", "h4", "summary") else 40
            if len(t) < minlen:
                continue
        if t in seen or is_boiler(el):
            continue
        seen.add(t)
        blocks.append((el.name, t))
    main_text = "\n".join(("\n## " + t if n in ("h1", "h2", "h3", "h4") else t) for n, t in blocks)
    body_text_only = "\n".join(t for n, t in blocks if n not in ("h1", "h2", "h3", "h4"))

    def content_lists():
        out = []
        for l in body.find_all(["ul", "ol"]):
            if is_boiler(l):
                continue
            lis = l.find_all("li", recursive=False)
            txt = norm(l.get_text(" "))
            if len(lis) < 2 or len(txt) < 80:
                continue
            linked = sum(len(norm(a.get_text(" "))) for a in l.find_all("a"))
            out.append({"items": len(lis), "kind": "link-list" if linked > 0.7 * len(txt) else "content", "sample": norm(lis[0].get_text(" "))[:90]})
        return out
    lists = content_lists()
    tables = []
    for t in body.find_all("table"):
        rows = t.find_all("tr")
        if len(rows) >= 2:
            tables.append({"rows": len(rows), "header": [norm(c.get_text(" "))[:40] for c in rows[0].find_all(["th", "td"])][:8],
                           "first_col": [norm(r.find(["th", "td"]).get_text(" "))[:30] for r in rows[1:6] if r.find(["th", "td"])]})
    imgs = [i for i in body.find_all("img") if not is_boiler(i)]
    def big(i):
        src = (i.get("src") or i.get("data-src") or i.get("srcset") or "").lower()
        if not src or src.startswith("data:image/svg") or ".svg" in src or "icon" in src or "logo" in src or "flag" in src:
            return False
        try:
            return int(str(i.get("width") or "999").replace("px", "")) >= 100
        except ValueError:
            return True
    content_imgs = [i for i in imgs if big(i)]
    videos = len(body.find_all("video")) + len([f for f in body.find_all("iframe") if re.search(r"youtube|youtu\.be|vimeo|wistia", (f.get("src") or f.get("data-src") or ""), re.I)])

    faq_heads = [o["text"] for o in outline if FAQ_RE.search(o["text"])]
    q_heads = [o["text"] for o in outline if o["text"].endswith("?")]
    q_other = [norm(e.get_text(" ")) for e in body.find_all(["summary", "button", "dt", "h4", "h5", "strong"]) if norm(e.get_text(" ")).endswith("?") and 15 < len(norm(e.get_text(" "))) < 160]
    questions = list(dict.fromkeys(faq_ld + q_heads + q_other))
    faq = {"present": bool("FAQPage" in types or faq_heads or len(questions) >= 3), "schema_faqpage": "FAQPage" in types,
           "headings": faq_heads, "questions": questions[:40]}

    prices = PRICE_RE.findall(full_text)
    nums = sorted({int(re.sub(r"\D", "", re.split(r",\d{1,2}", p)[0]) or 0) for p in prices if p.lower().startswith("ab")} - {0})
    ctas = {}
    for e in body.find_all(["a", "button"]):
        t = norm(e.get_text(" "))
        if 3 < len(t) < 45 and CTA_RE.search(t) and not is_boiler(e):
            ctas[t] = ctas.get(t, 0) + 1
    selects = len(body.find_all("select")) + len(body.find_all("input"))
    search_words = sorted({m.lower() for m in SEARCH_RE.findall(full_text)})
    filt_words = sorted({m.lower() for m in re.findall(r"filter\w*|sortier\w*|sterne|hotelkategorie|verpflegung|preis bis|budget", full_text, re.I)})[:12]

    base = d.get("url") or url
    host = urlparse(base).netloc.replace("www.", "")
    links = []
    for a in body.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if urlparse(href).netloc.replace("www.", "") == host:
            links.append({"href": href, "anchor": norm(a.get_text(" "))[:80], "boiler": is_boiler(a)})
    head_txt = " | ".join(o["text"] for o in outline)
    reg_head = [r for r in REGIONS if re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", head_txt, re.I)]
    reg_links = sorted({r for r in REGIONS for l in links if not l["boiler"] and re.search(r"(?<!\w)" + re.escape(r) + r"(?!\w)", l["anchor"], re.I)})
    reg_text = {r: len(re.findall(r"(?<!\w)" + re.escape(r) + r"(?!\w)", main_text, re.I)) for r in REGIONS}
    season_heads = [o["text"] for o in outline if SEASON_RE.search(o["text"].lower())]
    months_text = {m: len(re.findall(r"(?<!\w)" + m + r"(?!\w)", main_text)) for m in MONTHS}
    month_table = any(sum(1 for m in MONTHS if m[:3].lower() in " ".join(t["header"] + t["first_col"]).lower()) >= 4 for t in tables)

    zones = {"title": title, "description": desc, "h1": " | ".join(h1), "headings": head_txt, "text": main_text}
    kws = {k: kw_presence(k, zones) for k in keywords}

    res.update({
        "ok": bool(h1) and not re.search(r"cookie|consent|access denied|forbidden", title, re.I),
        "fail_reason": None if h1 and not re.search(r"cookie|consent", title, re.I) else "consent wall / no page content rendered (title: %s)" % title,
        "title": title, "title_len": len(title), "description": desc, "description_len": len(desc), "h1": h1,
        "canonical": canon.get("href") if canon else None, "robots": robots.get("content") if robots else None,
        "outline": outline, "h2_count": sum(o["level"] == "h2" for o in outline), "h3_count": sum(o["level"] == "h3" for o in outline),
        "text_chars_nospace": nospace(body_text_only), "text_words": len(re.findall(r"\w+", body_text_only)),
        "text_with_headings_chars_nospace": nospace(main_text),
        "trafilatura_chars_nospace": nospace(d.get("extracted_text") or ""),
        "lists": {"content": sum(l["kind"] == "content" for l in lists), "link_lists": sum(l["kind"] == "link-list" for l in lists), "samples": lists[:12]},
        "tables": {"count": len(tables), "items": tables[:8]},
        "images": {"total": len(imgs), "content": len(content_imgs), "with_alt": sum(1 for i in content_imgs if norm(i.get("alt"))),
                   "alt_samples": [norm(i.get("alt"))[:70] for i in content_imgs if norm(i.get("alt"))][:10]},
        "videos": videos, "faq": faq,
        "prices": {"mentions": len(prices), "min_ab_price": nums[0] if nums else None, "samples": [norm(p) for p in prices[:6]]},
        "reviews": {"aggregate_rating_schema": rating, "mentions": len(REVIEW_RE.findall(full_text))},
        "filters": {"form_controls": selects, "search_form_words": search_words, "filter_words": filt_words,
                    "search_form": len(search_words) >= 2, "facets": any(w.startswith(("filter", "sortier")) for w in filt_words)},
        "cta": {"count": sum(ctas.values()), "top": sorted(ctas.items(), key=lambda x: -x[1])[:10]},
        "regions": {"block": len(reg_head) >= 3 or len(reg_links) >= 4, "in_headings": reg_head, "in_link_anchors": reg_links,
                    "mentions_in_text": {k: v for k, v in reg_text.items() if v}},
        "seasons": {"block": bool(season_heads) or month_table, "headings": season_heads, "month_table": month_table,
                    "months_in_text": {k: v for k, v in months_text.items() if v}},
        "schema_types": types,
        "keywords_found": kws,
        "keywords_exact_any": sorted(k for k, v in kws.items() if v["text"] or v["title"] or v["h1"] or v["headings"] or v["description"]),
        "internal_links_content": len([l for l in links if not l["boiler"]]),
        "main_text": main_text,
    })
    if url == OWN:
        res["internal_links"] = links
    return res


def serp_positions():
    pos = {}
    for f in glob.glob(os.path.join(ROOT, "serp-raw-regular", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        if d["keyword"] not in [MAIN_KW] + ADJACENT:
            continue
        for i in d["response"]["tasks"][0]["result"][0]["items"] or []:
            if i.get("type") == "organic":
                pos.setdefault(i["url"], {})[d["keyword"]] = i.get("rank_group")
    return pos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    wb = openpyxl.load_workbook(os.path.join(ROOT, "semantics-turkei.xlsx"), read_only=True)
    rows = list(wb["Ключі"].iter_rows(values_only=True))[1:]
    hub = sorted([r for r in rows if r[9] and str(r[9]).rstrip("/").endswith("/tour/turkei")], key=lambda r: -(r[4] or 0))
    keywords = [r[1] for r in hub]
    pos = serp_positions()

    comps, replaced, reserves = [], [], list(RESERVES)
    for u in COMPETITORS:
        r = analyse(u, keywords, a.refresh)
        print(f"{'OK ' if r['ok'] else 'FAIL'} {r.get('status')} {r.get('mode_used')} text={r.get('text_chars_nospace')} {u} {r.get('error') or ''}", flush=True)
        if not r["ok"]:
            while reserves:
                alt = reserves.pop(0)
                r2 = analyse(alt, keywords, a.refresh)
                print(f"  reserve {'OK ' if r2['ok'] else 'FAIL'} {r2.get('status')} text={r2.get('text_chars_nospace')} {alt}", flush=True)
                replaced.append({"failed": u, "status": r.get("status"), "error": r.get("error") or r.get("fail_reason"), "attempts": r.get("attempts"), "replacement": alt, "replacement_ok": r2["ok"]})
                if r2["ok"]:
                    r2["replaces"] = u
                    r = r2
                    break
        r["serp_positions"] = pos.get(r["url"], {})
        r["note"] = NOTES.get(r["url"])
        comps.append(r)
    own = analyse(OWN, keywords, a.refresh)
    print(f"OWN {own.get('status')} text={own.get('text_chars_nospace')}", flush=True)

    good = [c for c in comps if c["ok"]]
    def med(f):
        v = [f(c) for c in good]
        return statistics.median(v) if v else None
    summary = {"analysed_ok": len(good), "failed": [c["url"] for c in comps if not c["ok"]], "replaced": replaced,
               "median_text_chars_nospace": med(lambda c: c["text_chars_nospace"]),
               "min_text": min((c["text_chars_nospace"] for c in good), default=None), "max_text": max((c["text_chars_nospace"] for c in good), default=None),
               "median_h2": med(lambda c: c["h2_count"]), "median_h3": med(lambda c: c["h3_count"]),
               "median_content_images": med(lambda c: c["images"]["content"]),
               "with_faq": sum(c["faq"]["present"] for c in good), "with_tables": sum(c["tables"]["count"] > 0 for c in good),
               "with_content_lists": sum(c["lists"]["content"] > 0 for c in good), "with_region_block": sum(c["regions"]["block"] for c in good),
               "with_season_block": sum(c["seasons"]["block"] for c in good), "with_video": sum(c["videos"] > 0 for c in good),
               "with_prices": sum(c["prices"]["mentions"] > 0 for c in good), "with_reviews": sum(c["reviews"]["mentions"] > 0 for c in good)}
    json.dump({"main_keyword": MAIN_KW, "adjacent": ADJACENT, "hub_keywords": [{"keyword": r[1], "translation": r[2], "volume": r[4]} for r in hub],
               "summary": summary, "competitors": comps, "own": own}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", OUT)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
