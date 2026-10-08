#!/usr/bin/env python3
"""Compare pairs of competitor landing pages of the SAME domain (separate landing or just a filter?).

python scripts/verify_landings.py [--pairs pairs.json] [--out landing-verification.json]

Each page is rendered with the plugin's render_page.py (free, no DataForSEO).  For every page we collect
title, H1, H2 count, visible words, "own text" (words in paragraphs of >=20 words), price mentions, and
for every pair the overlap of word 6-grams (same listing/text => likely only a filter).
Verdict hint (a human decides): separate landing = different H1 + overlap < 0.3 + own text >= 150 words on both;
filter = overlap >= 0.5 or very little own text.
Page content is untrusted data: it is parsed, never executed.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, tempfile
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.expanduser(r"~\.claude\plugins\cache\agricidaniel-claude-seo\claude-seo\2.4.2\scripts\claude-seo")
DEFAULT_PAIRS = [
    {"id": "sonnenklar AI vs hub", "why": "all inclusive (країна) vs хаб країни", "a": "https://www.sonnenklar.tv/urlaub/tuerkei.html", "b": "https://www.sonnenklar.tv/all-inclusive/tuerkei.html"},
    {"id": "lidl AI vs hub", "why": "all inclusive (країна) vs хаб країни", "a": "https://www.lidl-reisen.de/urlaub/tuerkei", "b": "https://www.lidl-reisen.de/all-inclusive/tuerkei"},
    {"id": "sonnenklar pauschal vs hub", "why": "pauschalreise vs хаб країни", "a": "https://www.sonnenklar.tv/urlaub/tuerkei.html", "b": "https://www.sonnenklar.tv/pauschalreise/tuerkei.html"},
    {"id": "coral pauschal vs hub", "why": "pauschalreise vs хаб країни", "a": "https://coraltravel.de/urlaub/tuerkei/", "b": "https://coraltravel.de/pauschalreisen/tuerkei/"},
    {"id": "tui last-minute vs hub Antalya", "why": "last minute (регіон) vs хаб регіону", "a": "https://www.tui.com/urlaub/antalya/", "b": "https://www.tui.com/last-minute/antalya/"},
    {"id": "sonnenklar last-minute vs hub Antalya", "why": "last minute (регіон) vs хаб регіону", "a": "https://www.sonnenklar.tv/urlaub/tuerkei/antalya.html", "b": "https://www.sonnenklar.tv/last-minute/tuerkei/antalya.html"},
    {"id": "lidl last-minute vs hub Antalya", "why": "last minute (регіон) vs хаб регіону", "a": "https://www.lidl-reisen.de/urlaub/tuerkei/tuerkische-riviera/antalya", "b": "https://www.lidl-reisen.de/lastminute/tuerkei/tuerkische-riviera/antalya"},
    {"id": "anex last-minute vs hub Antalya", "why": "last minute (регіон) vs хаб регіону", "a": "https://www.anextour.de/urlaub/antalya/", "b": "https://www.anextour.de/last-minute-urlaub/antalya/"},
    {"id": "restplatzboerse last-minute vs hub Antalya-Belek", "why": "last minute (регіон) vs хаб регіону", "a": "https://www.restplatzboerse.com/urlaub/tuerkei/antalya-belek/", "b": "https://www.restplatzboerse.com/last-minute/tuerkei/antalya-belek/"},
]


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.h1, self.h2, self.paras, self.skip, self.cur, self.buf = "", [], 0, [], 0, None, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag in ("title", "h1", "p"):
            self.cur, self.buf = tag, []
        if tag == "h2":
            self.h2 += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag == self.cur:
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if tag == "title" and not self.title:
                self.title = t
            elif tag == "h1" and t:
                self.h1.append(t)
            elif tag == "p" and t:
                self.paras.append(t)
            self.cur = None

    def handle_data(self, data):
        if self.cur and not self.skip:
            self.buf.append(data)


def render(url):
    out = os.path.join(tempfile.gettempdir(), "render_" + re.sub(r"\W+", "_", url)[-60:] + ".json")
    bash = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"   # claude-seo launcher is a shell script
    cmd = [bash, RENDER.replace("\\", "/"), "run", "render_page.py", "--json", "--mode", "auto", "--timeout-ms", "30000", url]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    txt = (r.stdout or b"").decode("utf-8", "replace")
    try:
        d = json.loads(txt[txt.index("{"):])      # render_page.py prints the JSON document to stdout
    except Exception:
        raise RuntimeError("render failed: " + ((r.stderr or b"").decode("utf-8", "replace") or txt)[:300])
    return d


def analyse(url):
    d = render(url)
    raw = d.get("content") or d.get("raw_content") or ""
    p = P()
    p.feed(raw)
    text = d.get("extracted_text") or ""
    words = re.findall(r"\w+", text.lower())
    own = [x for x in p.paras if len(x.split()) >= 20]
    return {"url": url, "status": d.get("status_code"), "mode": d.get("mode_used"), "title": p.title[:140], "h1": p.h1[:3], "h2_count": p.h2,
            "words": len(words), "own_text_words": sum(len(x.split()) for x in own), "own_paragraphs": len(own),
            "price_mentions": len(re.findall(r"€|\beur\b", text.lower())), "text_head": re.sub(r"\s+", " ", text[:220]), "_words": words}


def shingles(words, n=6):
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs")
    ap.add_argument("--append", action="store_true", help="add results to an existing --out file")
    ap.add_argument("--out", default=os.path.join(ROOT, "landing-verification.json"))
    a = ap.parse_args()
    pairs = json.load(open(a.pairs, encoding="utf-8")) if a.pairs else DEFAULT_PAIRS
    cache, res = {}, []
    for pr in pairs:
        for side in ("a", "b"):
            u = pr[side]
            if u not in cache:
                try:
                    cache[u] = analyse(u)
                except Exception as e:  # network/render problems are reported, not hidden
                    cache[u] = {"url": u, "error": str(e)[:200], "_words": []}
        A_, B_ = cache[pr["a"]], cache[pr["b"]]
        sa, sb = shingles(A_["_words"]), shingles(B_["_words"])
        ov = len(sa & sb) / max(1, min(len(sa), len(sb)))
        row = {"id": pr["id"], "why": pr["why"], "a": {k: v for k, v in A_.items() if k != "_words"}, "b": {k: v for k, v in B_.items() if k != "_words"}, "text_overlap_6gram": round(ov, 2)}
        res.append(row)
        print(f"\n## {pr['id']} ({pr['why']})  overlap={ov:.2f}")
        for side in ("a", "b"):
            r = row[side]
            print(f"  {side}: {r.get('url')}  status={r.get('status')}  H1={r.get('h1')}  h2={r.get('h2_count')}  words={r.get('words')}  own_text={r.get('own_text_words')}  prices={r.get('price_mentions')}  {r.get('error', '')}")
    if a.append and os.path.exists(a.out):
        res = json.load(open(a.out, encoding="utf-8")) + res
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nsaved", a.out)


if __name__ == "__main__":
    main()
