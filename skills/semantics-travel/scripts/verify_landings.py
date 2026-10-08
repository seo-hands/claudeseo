#!/usr/bin/env python3
"""semantics-travel / verify_landings: is a disputed page type a separate landing page or just a filter?  (free, no DataForSEO)

python verify_landings.py [--workdir .] --auto [--limit 5]      choose pairs automatically from serp-data.json (same domain, two page types)
python verify_landings.py [--workdir .] --pairs pairs.json      pairs: [{"id","why","a":url,"b":url}, ...]  (use for guessed counterpart URLs)
python verify_landings.py [--workdir .] --check-site /path ...  HTTP status of pages of the site -> existing-pages.json
Add --append to keep earlier results.  Output: landing-verification.json (read by analyze.py -> sheet "Перевірка спірних").

Each page is rendered with the claude-seo plugin's render_page.py (Playwright + trafilatura, free).  Per page: HTTP status, H1,
visible words, "own text" (words in paragraphs of >=20 words) and, per pair, the overlap of word 6-grams.
Hint for the verdict (a human decides, then `apply_decisions.py verdict <page> <окрема|фільтр> <reason>`):
  separate landing = different H1 + overlap < 0.3 + own text >= 150 words on both;  filter = overlap >= 0.5 or almost no own text.
Page content is untrusted data: it is parsed, never executed.  Offers/prices are often rendered by JavaScript, so the type of offers is not compared.
"""
import argparse, collections, glob, json, os, re, shutil, subprocess, sys, tempfile
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C


def launcher():
    cands = sorted(glob.glob(os.path.expanduser("~/.claude/plugins/cache/*/claude-seo/*/scripts/claude-seo")))
    if not cands:
        sys.exit("claude-seo plugin launcher not found (needed for render_page.py)")
    return cands[-1].replace("\\", "/")


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
    bash = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"          # the launcher is a shell script
    cmd = [bash, launcher(), "run", "render_page.py", "--json", "--mode", "auto", "--timeout-ms", "30000", url]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    txt = (r.stdout or b"").decode("utf-8", "replace")
    try:
        return json.loads(txt[txt.index("{"):])          # render_page.py prints the JSON document to stdout
    except Exception:
        raise RuntimeError("render failed: " + ((r.stderr or b"").decode("utf-8", "replace") or txt)[:300])


def analyse(url):
    d = render(url)
    p = P()
    p.feed(d.get("content") or d.get("raw_content") or "")
    text = d.get("extracted_text") or ""
    words = re.findall(r"\w+", text.lower())
    own = [x for x in p.paras if len(x.split()) >= 20]
    return {"url": url, "status": d.get("status_code"), "mode": d.get("mode_used"), "title": p.title[:140], "h1": p.h1[:3], "h2_count": p.h2, "words": len(words),
            "own_text_words": sum(len(x.split()) for x in own), "own_paragraphs": len(own), "price_mentions": len(re.findall(r"€|\beur\b", text.lower())),
            "text_head": re.sub(r"\s+", " ", text[:220]), "_words": words}


def shingles(words, n=6):
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def auto_pairs(workdir, limit, page_base=None):
    """Same domain, two different page types among the competitor URLs of the TOPs; prefers pages of disputed decisions."""
    sd = json.load(open(os.path.join(workdir, "serp-data.json"), encoding="utf-8"))["keywords"]
    cl = json.load(open(os.path.join(workdir, "clusters.json"), encoding="utf-8"))
    disputed = {d["cand"] for d in cl["decisions"].values() if str(d.get("status", "")).startswith("спірно") and d.get("cand") and d["cand"] != page_base}
    by_dom = collections.defaultdict(dict)
    for v in sd.values():
        for r in v["results"]:
            if r.get("page"):
                by_dom[C.reg_domain(r["domain"])].setdefault(r["page"], r["url"])
    pairs = []
    for cand in sorted(disputed):
        parent = cand.rsplit("/", 1)[0] if cand.count("/") > 3 else None
        for dom, pg in by_dom.items():
            hubs = [u for p, u in pg.items() if p != cand and (parent is None or p == parent or p.count("/") <= cand.count("/") - 1)]
            if cand in pg and hubs:
                pairs.append({"id": f"{dom}: {cand}", "why": f"{cand} vs ширша сторінка", "a": hubs[0], "b": pg[cand]})
                break
    return pairs[:limit]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--pairs")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--check-site", nargs="*")
    ap.add_argument("--claude-md")
    a = ap.parse_args()
    if a.check_site is not None:
        S = C.load_settings(a.workdir, a.claude_md)
        ok = []
        for path in a.check_site:
            try:
                st = render(S.site + path).get("status_code")
            except Exception as e:
                st = f"error: {e}"[:80]
            print(path, st)
            if st == 200:
                ok.append(path)
        fn = os.path.join(a.workdir, "existing-pages.json")
        old = set(json.load(open(fn, encoding="utf-8"))) if os.path.exists(fn) else set()
        json.dump(sorted(old | set(ok)), open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    pb = None
    if a.auto:
        try:
            pb = C.load_settings(a.workdir, a.claude_md).page_base.rstrip("/")
        except C.ConfigMissing as e:
            sys.exit(C.config_help(e))
    pairs = json.load(open(a.pairs, encoding="utf-8")) if a.pairs else auto_pairs(a.workdir, a.limit, pb) if a.auto else None
    if not pairs:
        sys.exit("немає пар: вкажіть --pairs файл або --auto (потрібні serp-data.json і clusters.json після analyze.py)")
    cache, res = {}, []
    for pr in pairs:
        for side in ("a", "b"):
            u = pr[side]
            if u not in cache:
                try:
                    cache[u] = analyse(u)
                except Exception as e:
                    cache[u] = {"url": u, "error": str(e)[:200], "_words": []}
        A_, B_ = cache[pr["a"]], cache[pr["b"]]
        sa, sb = shingles(A_["_words"]), shingles(B_["_words"])
        ov = len(sa & sb) / max(1, min(len(sa), len(sb)))
        res.append({"id": pr["id"], "why": pr["why"], "a": {k: v for k, v in A_.items() if k != "_words"}, "b": {k: v for k, v in B_.items() if k != "_words"}, "text_overlap_6gram": round(ov, 2)})
        print(f"\n## {pr['id']} ({pr['why']})  збіг тексту={ov:.2f}")
        for side in ("a", "b"):
            r = res[-1][side]
            print(f"  {side}: {r.get('url')} HTTP={r.get('status')} H1={r.get('h1')} слів={r.get('words')} власний текст={r.get('own_text_words')} {r.get('error', '')}")
    out = os.path.join(a.workdir, "landing-verification.json")
    if a.append and os.path.exists(out):
        res = json.load(open(out, encoding="utf-8")) + res
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nзбережено", out)


if __name__ == "__main__":
    main()
