#!/usr/bin/env python3
"""Free page checks for stage-2 candidates: external links in the article body separately from the template, rel,
niche of the targets; the latest materials of the advertising section; risky links on the homepage and whether they
are site-wide.  Pages are cached in cache/<domain>/pages/<md5 of URL>.html.  Writes pages.json.

What to open comes from site-notes.json: `articles` (up to 3 URLs), `ad_section_url` (+ optional `ad_listing_pattern`,
a regex for article URLs of the section).  Without `articles` the script takes paid-looking pages found by the SERP
queries of stage 1.  A page that answers 403 is not retried - it goes to the manual check list."""
import hashlib, os, re, sys, urllib.request
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import bl_common as bl

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.7,en;q=0.5", "Accept": "text/html,application/xhtml+xml"}
BODY_SELECTORS = ["[itemprop=articleBody]", ".entry-content", ".post-content", ".article-content", ".article__text", ".article-text", ".news-text", ".news-detail",
                  ".detail_text", ".itemFullText", ".content-text", ".post__text", ".text", "article", "main", "#content", ".content"]


def get(run, domain, url):
    """(status, html). 200 answers are cached; offline only the cache is used."""
    p = os.path.join(run.cache, domain, "pages", hashlib.md5(url.encode()).hexdigest() + ".html")
    if os.path.exists(p):
        return 200, open(p, encoding="utf-8", errors="ignore").read()
    if run.offline:
        return 0, ""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
            raw = r.read()
            cs = r.headers.get_content_charset()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return -1, ""
    if not cs:
        m = re.search(rb"charset=[\"']?([\w-]+)", raw[:3000])
        cs = m.group(1).decode() if m else "utf-8"
    try:
        html = raw.decode(cs)
    except Exception:
        html = raw.decode("utf-8", "ignore") if b"\xd0" in raw[:4000] else raw.decode("cp1251", "ignore")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(html)
    return 200, html


def links(el, dom):
    out = []
    for a in el.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("http"):
            continue
        r = bl.reg_domain(urlparse(h).hostname or "")
        if not r or r == bl.reg_domain(dom) or r in bl.SOCIAL:
            continue
        rel = " ".join(a.get("rel") or [])
        kind = "sponsored" if "sponsored" in rel else ("nofollow" if "nofollow" in rel else "dofollow")
        anchor = " ".join(a.get_text(" ").split())[:60]
        out.append({"domain": r, "rel": kind, "anchor": anchor, "href": h, "niche": bl.niche(r + " " + anchor + " " + h)})
    return out


def body_of(s):
    for sel in BODY_SELECTORS:
        for el in s.select(sel):
            if len(el.get_text(" ", strip=True)) > 500:
                return el, sel
    return s.body or s, "body"


def article(run, dom, url):
    st, html = get(run, dom, url)
    if st != 200:
        return {"url": url, "status": st}
    s = BeautifulSoup(html, "html.parser")
    title = " ".join((s.title.get_text() if s.title else "").split())[:120]
    body, sel = body_of(s)
    allx, bx = links(s, dom), links(body, dom)
    keys = {(l["href"], l["anchor"]) for l in bx}
    tmpl = [l for l in allx if (l["href"], l["anchor"]) not in keys] if sel != "body" else []
    return {"url": url, "status": 200, "title": title, "body_selector": sel, "split": sel != "body", "words": len(body.get_text(" ", strip=True).split()),
            "body": bx[:12], "body_n": len(bx), "tmpl_n": len(tmpl) if sel != "body" else None, "tmpl_domains": sorted({l["domain"] for l in tmpl})[:15],
            "niche": bl.niche(title + " " + url) or next((l["niche"] for l in bx if l["niche"]), "")}


def listing(run, dom, url, pattern, n=15):
    st, html = get(run, dom, url)
    if st != 200:
        return {"url": url, "status": st, "items": [], "risky_share": None}
    s = BeautifulSoup(html, "html.parser")
    rx = re.compile(pattern) if pattern else None
    seen = {}
    for a in s.find_all("a", href=True):
        h = urljoin(url, a["href"]).split("#")[0]
        t = " ".join(a.get_text(" ").split())
        if len(t) < 23 or bl.reg_domain(urlparse(h).hostname or "") != bl.reg_domain(dom):
            continue
        if rx and not rx.search(h):
            continue
        seen.setdefault(h, t)
    items = [{"url": h, "title": t[:140], "niche": bl.niche(t + " " + h)} for h, t in list(seen.items())[:n]]
    risky = sum(1 for i in items if i["niche"])
    return {"url": url, "status": 200, "items": items, "risky": risky, "risky_share": round(risky / len(items), 3) if items else None}


def homepage(run, dom, inner):
    """Risky external links on the homepage; when there are some - are they also on 2-4 inner pages (site-wide)."""
    home = "https://" + dom + "/"
    st, html = get(run, dom, home)
    if st != 200:
        st, html = get(run, dom, "https://www." + dom + "/")
    if st != 200:
        return {"status": st, "risky": [], "sitewide": None, "inner_checked": []}
    s = BeautifulSoup(html, "html.parser")
    ext = links(s, dom)
    risky = [l for l in ext if l["niche"]]
    out = {"status": 200, "ext_n": len(ext), "ext_domains": sorted({l["domain"] for l in ext})[:40], "risky": risky, "sitewide": None, "inner_checked": []}
    if risky:
        if not inner:
            for a in s.find_all("a", href=True):
                h = urljoin(home, a["href"]).split("#")[0]
                if bl.reg_domain(urlparse(h).hostname or "") == bl.reg_domain(dom) and len(urlparse(h).path) > 1 and h not in inner:
                    inner.append(h)
                if len(inner) >= 3:
                    break
        found = 0
        for u in inner[:4]:
            st2, h2 = get(run, dom, u)
            if st2 != 200:
                out["inner_checked"].append({"url": u, "status": st2})
                continue
            doms2 = {l["domain"] for l in links(BeautifulSoup(h2, "html.parser"), dom)}
            hit = sorted(doms2 & {r["domain"] for r in risky})
            found += 1 if hit else 0
            out["inner_checked"].append({"url": u, "status": 200, "risky_domains": hit})
        ok = [x for x in out["inner_checked"] if x["status"] == 200]
        out["sitewide"] = (found >= max(1, len(ok) // 2 + 1)) if len(ok) >= 2 else None
    return out


def collect(run, candidates):
    notes = run.load("site-notes.json", {})
    s1 = run.load("stage1.json") or {}
    P = {}
    for d in candidates:
        n = notes.get(d) or {}
        serp = ((s1.get("domains") or {}).get(d) or {}).get("serp") or {}
        urls = list(n.get("articles") or [])
        if not urls:
            for q, wanted in (("casino", "казино/ставки"), ("credit", "кредити/фінанси"), ("adv", None)):
                for i in (serp.get(q) or {}).get("own", []):
                    if (wanted and bl.is_risky_pr(i, wanted)) or (not wanted and not bl.NEWS.search(i["title"] + i["url"])):
                        if i["url"] not in urls:
                            urls.append(i["url"])
        p = P[d] = {"articles": [article(run, d, u) for u in urls[:4]]}
        if n.get("status") == 403:
            p["home"] = {"status": 403, "risky": [], "sitewide": None, "inner_checked": []}
        else:
            p["home"] = homepage(run, d, list(n.get("inner_pages") or []))
        p["listing"] = listing(run, d, n["ad_section_url"], n.get("ad_listing_pattern") or "") if n.get("ad_section_url") else None
    run.save("pages.json", P)
    return P


def main():
    ap = bl.parser(__doc__.split("\n")[0])
    ap.add_argument("--candidates", default="", help="домени через кому (інакше — кандидати зі stage1.json)")
    a = ap.parse_args()
    if not a.run:
        sys.exit("потрібен --run")
    run = bl.Run(a)
    s1 = run.load("stage1.json") or {}
    cands = [bl.norm_domain(x) for x in a.candidates.split(",") if x.strip()] or s1.get("candidates") or s1.get("candidates_auto") or []
    P = collect(run, cands)
    for d, p in P.items():
        h = p["home"]
        print(f"\n## {d} | головна: {h['status']}, ризикових посилань {len(h['risky'])}" + (f", наскрізні: {h['sitewide']}" if h["risky"] else ""))
        for r in h["risky"]:
            print(f"   головна → {r['domain']} ({r['rel']}, {r['niche']})")
        if p["listing"]:
            l = p["listing"]
            print(f"   рекламний розділ {l['url']}: {l['status']}, матеріалів {len(l['items'])}, ризикових {l.get('risky')}")
        for x in p["articles"]:
            if x["status"] != 200:
                print(f"   стаття {x['status']}: {x['url'][:100]}")
                continue
            print(f"   стаття: {x['title'][:70]} | тіло {x['body_n']}, шаблон {x['tmpl_n'] if x['split'] else 'не відокремлено'} | "
                  + ", ".join(f"{l['domain']} ({l['rel']}{', ' + l['niche'] if l['niche'] else ''})" for l in x["body"][:4]))


if __name__ == "__main__":
    main()
