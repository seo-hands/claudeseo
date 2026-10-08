#!/usr/bin/env python3
"""Step c: semantic similarity with a local open embedding model (free, no API).

python embed_terms.py --workdir . --page <URL>

Input: competitors-<slug>.json.  Output: embeddings-<slug>.json
 1) page keywords vs the main / adjacent keywords: tiers thr_core / thr_mid — a hint; the final place of a keyword
    is decided by volume and by the TOP;
 2) semantic words from competitor texts: the criterion is "present on >= N competitor pages"; similarity is only
    a column to sort by.  Navigation, competitor brands, cookie texts and generic words are cut with the stop list
    (references/stoplist_<lang>.txt + stop_brands of the market profile + competitor domains); duplicates are merged
    case-insensitively;
 3) subtopics: competitor H2/H3 clustered at topic_threshold; gap = topic on >= N competitors and absent on the own
    page.  "Present" needs both a similar own heading AND the topic words in the own body text.
The model lives in a permanent folder (models_dir), not in Temp.  Similarity comes from an open model, not from Google.
"""
import argparse, os, re, sys
from collections import Counter, defaultdict

import numpy as np

import tz_common as tz

TOK = re.compile(r"[A-Za-zÀ-ÿğışçİĞŞ][A-Za-zÀ-ÿğışçİĞŞ\-]*[A-Za-zÀ-ÿğışçİĞŞ]|\d{4}")
ENDINGS = ("s", "n", "en", "e", "es", "er")


def load_stop(ctx):
    path = os.path.join(tz.SKILL_DIR, "references", ctx["T"].get("stoplist", "stoplist_de.txt"))
    if not os.path.exists(path):
        tz.die(f"немає стоп-списку {path} (ключ tz.stoplist у профілі ринку).")
    words, single, cur = set(), set(), None
    for line in open(path, encoding="utf-8"):
        if line.lstrip().startswith("# @single"):
            cur = single            # the lines below: noise only as standalone terms, fine inside multi-word terms
        (words if cur is None else cur).update(line.split("#")[0].strip().lower().split())
    return words, single


def load_model(ctx):
    """primary model from the permanent folder; fallback model only with a loud note"""
    from fastembed import TextEmbedding
    cache = ctx["cfg"]["models_dir"]
    os.makedirs(cache, exist_ok=True)
    info = {"cache_dir": cache, "fallback_used": False, "downloaded": False, "errors": []}
    for i, name in enumerate([ctx["T"]["embed"]["model"], ctx["T"]["embed"].get("fallback")]):
        if not name:
            continue
        for local in (True, False):
            try:
                m = TextEmbedding(model_name=name, cache_dir=cache, local_files_only=local)
                info.update(model=name, fallback_used=i > 0, downloaded=not local)
                return m, info
            except Exception as e:
                info["errors"].append(f"{name} ({'локальний кеш' if local else 'завантаження'}): {type(e).__name__}: {str(e)[:160]}")
    print("MODEL LOAD FAILED:\n" + "\n".join(info["errors"]), file=sys.stderr)
    sys.exit(2)


def main():
    ap = tz.args_page(argparse.ArgumentParser())
    a = ap.parse_args()
    ctx = tz.load_ctx(a.workdir, a.page)
    cfg, T = ctx["cfg"], ctx["T"]
    if not os.path.exists(ctx["f"]["competitors"]):
        tz.die("немає competitors-<slug>.json. Спершу analyze_competitors.py.")
    data = tz.rjson(ctx["f"]["competitors"])
    comps, own = [c for c in data["competitors"] if c.get("ok")], data["own"]
    N = len(comps)
    main_kw, adjacent = data["main_keyword"], data["adjacent"]
    refs = [main_kw] + adjacent
    STOP, STOP_SINGLE = load_stop(ctx)
    glue = set(T["term_glue"])
    brand_rx = [re.compile(b, re.I) for b in ctx["P"].get("stop_brands", [])]
    brand_tokens = set()
    generic = set(ctx["P"].get("tokens", {}).get("generic", [])) | {"travel", "tour", "tours", "holiday", "holidays"}
    for c in comps:      # brand = the registrable domain name, without generic travel words ("reisen", "urlaub")
        label = tz.sp.reg_domain(tz.host(c["url"])).split(".")[0].lower()
        brand_tokens.update(t for t in [label] + re.split(r"[\W_]+", label) if len(t) >= 4 and t not in generic)
    is_brand = lambda w: w in brand_tokens or any(r.fullmatch(w) for r in brand_rx)
    topic_words = set(re.findall(r"\w+", main_kw.lower())) | set(re.findall(r"\w+", ctx["S"]["country"].lower()))
    entities = T.get("entities", {}).get(ctx["S"]["slug"], [])

    ent_tokens = {w for e in entities for w in e.lower().split()} | {r.lower() for r in (ctx["S"].get("regions") or {})}
    ent_full = {e.lower() for e in entities}

    model, minfo = load_model(ctx)

    def embed(texts):
        v = np.array(list(model.embed(list(texts), batch_size=64)), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    R = embed(refs)

    # ---- 1) page keywords
    kws = data["hub_keywords"]
    S_ = embed([k["keyword"] for k in kws]) @ R.T
    a_rows = []
    for k, s in zip(kws, S_):
        adj = {adjacent[i]: round(float(s[i + 1]), 3) for i in range(len(adjacent))}
        best = max(adj, key=adj.get) if adj else None
        sm = float(s[0])
        a_rows.append({"keyword": k["keyword"], "translation": k["translation"], "volume": k["volume"], "sim_main": round(sm, 3), "sim_adjacent": adj,
                       "closest_adjacent": best, "sim_closest_adjacent": adj.get(best),
                       "tier": "ядро" if sm >= cfg["thr_core"] else ("H2/текст" if sm >= cfg["thr_mid"] else "FAQ/довгий хвіст"),
                       "head_word_of_other_page": tz.flag_keyword(ctx, k["keyword"])})

    # ---- 2) semantic words
    def good(t):
        w = t.lower()
        return w not in STOP and len(w) > 2 and not is_brand(w)

    def terms_of(text):
        out = defaultdict(list)
        for sent in re.split(r"(?<=[.!?:])\s+|\n+|[•|–—]", text):
            toks = TOK.findall(sent)
            for i, t in enumerate(toks):
                if t[0].isupper() and good(t) and len(t) >= 4 and not t.isdigit() and t.lower() not in STOP_SINGLE:
                    out[t.lower()].append((t, i == 0))
                for n in (2, 3):
                    g = toks[i:i + n]
                    if len(g) < n or not good(g[0]) or not good(g[-1]) or any(is_brand(x.lower()) for x in g):
                        continue
                    if not any(x[0].isupper() and x.lower() not in STOP for x in (g[1:] if i == 0 else g)):
                        continue
                    if n == 3 and g[1].lower() in STOP and g[1].lower() not in glue:
                        continue
                    if all(x.lower() in ent_tokens or x.lower() in glue for x in g):
                        continue      # an enumeration of place names ("Side Alanya") is not a term
                    if " ".join(x.lower() for x in g) in ent_full:
                        continue      # counted once below as an entity
                    out[" ".join(x.lower() for x in g)].append((" ".join(g), False))
        low = text.lower()
        for e in entities:
            if re.search(r"(?<!\w)" + re.escape(e.lower()) + r"(?!\w)", low):
                out[e.lower()].append((e, False))
        return out

    df, forms, tf = Counter(), defaultdict(Counter), Counter()
    for c in comps:
        text = "\n".join(l[3:] if l.startswith("## ") else l for l in c["main_text"].split("\n") if l.strip())
        for k, occ in terms_of(text).items():
            if " " not in k and len(occ) < 2 and all(first for _, first in occ):
                continue  # seen once, sentence-initial and capitalised: probably not a noun
            df[k] += 1
            tf[k] += len(occ)
            for f, _ in occ:
                forms[k][f] += 1
    cand = [k for k, n in df.items() if n >= cfg["term_min_competitors"]]
    # merge inflected variants of one word and of multi-word terms (case-insensitive keys already merged)
    merged = {}
    stem = lambda k: " ".join(re.sub(r"(en|er|es|e|n|s)$", "", w) if len(w) > 5 else w for w in k.split())
    for k in sorted(cand, key=lambda x: (-df[x], len(x))):
        base = next((m for m in merged if m != k and (stem(m) == stem(k) or (" " not in k and " " not in m and k.startswith(m) and k[len(m):] in ENDINGS))), None)
        if base:
            merged[base]["variants"].append(k)
            merged[base]["df"] = max(merged[base]["df"], df[k])
        else:
            merged[k] = {"variants": [], "df": df[k]}
    cand = list(merged)
    longer = [k for k in cand if " " in k]
    cand = [k for k in cand if not any(k != l and re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", l) and merged[l]["df"] >= merged[k]["df"] for l in longer)]
    ST = embed([forms[k].most_common(1)[0][0] for k in cand]) @ R.T if cand else np.zeros((0, len(refs)))
    b_rows = []
    for k, s in zip(cand, ST):
        best = int(np.argmax(s))
        other = next((b for b in ctx["banned"] if re.search(b["match"], k, re.I)), None)
        b_rows.append({"term": forms[k].most_common(1)[0][0], "competitors": merged[k]["df"], "of": N, "occurrences": tf[k], "variants": merged[k]["variants"],
                       "sim_main": round(float(s[0]), 3), "sim_best": round(float(s[best]), 3), "closest_ref": refs[best],
                       "kind": "сутність" if k in [e.lower() for e in entities] else ("слово" if " " not in k else f"{len(k.split())}-грама"),
                       "contains_page_keyword": bool(topic_words & set(k.split())),
                       "head_word_of_other_page": other["label"] if other else None, "other_page": other["page"] if other else None})
    b_rows.sort(key=lambda r: (-r["competitors"], -r["sim_best"]))
    b_rows = b_rows[:cfg["term_max"]]

    # ---- 3) subtopics
    def strip_topic(t):
        """headings are clustered by their subtopic: the words of the page's own topic are removed first"""
        if not cfg.get("topic_strip_page_words", True):
            return t
        out = " ".join(w for w in re.split(r"\s+", t) if re.sub(r"\W", "", w.lower()) not in topic_words)
        return out if len(re.findall(r"\w{3,}", out)) >= 1 else ""

    heads = []
    for c in comps:
        seen = set()
        for o in c["outline"]:
            t = o["text"].strip()
            if len(t) < 4 or t.lower() in seen:
                continue
            seen.add(t.lower())
            heads.append({"host": tz.host(c["url"]), "level": o["level"], "text": t, "core": strip_topic(t)})
    heads = [h for h in heads if h["core"]]
    H = embed([h["core"] for h in heads])
    SIM = H @ H.T
    clusters = [[i] for i in range(len(heads))]
    thr = cfg["topic_threshold"]
    while len(clusters) > 1:   # agglomerative, average linkage
        best, bi, bj = -1, -1, -1
        cents = np.array([H[c].mean(axis=0) for c in clusters])
        cents /= np.linalg.norm(cents, axis=1, keepdims=True)
        CS = cents @ cents.T
        np.fill_diagonal(CS, -1)
        for i, j in zip(*np.unravel_index(np.argsort(-CS, axis=None)[:60], CS.shape)):
            if i < j:
                avg = float(SIM[np.ix_(clusters[i], clusters[j])].mean())
                if avg > best:
                    best, bi, bj = avg, i, j
        if best < thr:
            break
        clusters[bi] += clusters[bj]
        del clusters[bj]
    own_heads = [o["text"] for o in own.get("outline", [])]          # H1 is the page topic, not a subtopic
    own_cores = [strip_topic(t) or t for t in own_heads]
    OH = embed(own_cores) if own_cores else np.zeros((0, H.shape[1]), dtype=np.float32)
    own_text = (own.get("body_text") or "").lower()
    c_rows = []
    for cl in clusters:
        hosts = sorted({heads[i]["host"] for i in cl})
        cent = H[cl].mean(axis=0)
        cent /= np.linalg.norm(cent)
        label = heads[cl[int(np.argmax(H[cl] @ cent))]]["text"]
        # words of the topic: used by several competitors in the headings of the cluster
        wh = defaultdict(set)
        for i in cl:
            for w in set(TOK.findall(heads[i]["core"])):
                wl = w.lower()
                if len(wl) >= 4 and wl not in STOP and wl not in topic_words and not is_brand(wl) and not wl.isdigit():
                    wh[re.sub(r"(en|er|es|e|n|s)$", "", wl) if len(wl) > 5 else wl].add(heads[i]["host"])
        need = max(1, min(2, len(hosts)))
        words = [w for w, hs in sorted(wh.items(), key=lambda x: (-len(x[1]), x[0])) if len(hs) >= need][:6]
        found = [w for w in words if w in own_text]
        text_ok = (len(found) / len(words) >= cfg["topic_text_share"]) if words else None
        own_sim, own_match = 0.0, None
        if len(OH):
            m = OH @ H[cl].T
            own_sim, own_match = float(m.max()), own_heads[int(np.argmax(m.max(axis=1)))]
        head_ok = own_sim >= thr
        present = head_ok and text_ok is True
        status = ("так" if present else "лише заголовок або блок посилань, тексту немає" if head_ok and text_ok is False
                  else "заголовок схожий, слів теми для перевірки тексту немає" if head_ok else "є в тексті без заголовка" if text_ok else "ні")
        c_rows.append({"subtopic": label, "competitors": len(hosts), "of": N, "hosts": hosts,
                       "headings": [f"{heads[i]['host']}: {heads[i]['text']}" for i in cl], "topic_words": words, "topic_words_in_own_text": found,
                       "sim_main": round(float(cent @ R[0]), 3), "own_best_sim": round(own_sim, 3), "own_best_heading": own_match,
                       "own_heading_match": head_ok, "own_text_match": text_ok, "on_own_page": present, "own_status": status,
                       "gap": len(hosts) >= cfg["gap_min_competitors"] and not present})
    c_rows.sort(key=lambda r: (-r["competitors"], -len(r["headings"])))

    out = {"page": ctx["url"], "model": minfo["model"], "model_info": minfo,
           "note": "Близькість рахує відкрита модель, а не Google: орієнтир поруч із частотністю й аналізом ТОП, а не замість них.",
           "thresholds": {"core": cfg["thr_core"], "mid": cfg["thr_mid"], "term_min_competitors": cfg["term_min_competitors"],
                          "topic": thr, "gap_min_competitors": cfg["gap_min_competitors"], "topic_text_share": cfg["topic_text_share"]},
           "references": refs, "competitors_used": [c["url"] for c in comps], "keywords": a_rows, "terms": b_rows,
           "subtopics": [r for r in c_rows if r["competitors"] >= 2], "subtopic_singletons": [r for r in c_rows if r["competitors"] < 2],
           "headings_total": len(heads), "own_headings": own_heads}
    tz.wjson(ctx["f"]["embeddings"], out)
    print(f"модель: {minfo['model']} | папка: {minfo['cache_dir']} | "
          + ("УВАГА: спрацювала РЕЗЕРВНА модель" if minfo["fallback_used"] else "основна модель")
          + (" | модель ЗАВАНТАЖЕНО ЗАНОВО (у папці її не було)" if minfo["downloaded"] else " | з локальної папки") + f" | конкурентів: {N}")
    for e in minfo["errors"]:
        print("  примітка:", e)
    print("\n1) ключі:", dict(Counter(r["tier"] for r in a_rows)))
    for r in sorted(a_rows, key=lambda r: -r["sim_main"]):
        print(f"  {r['sim_main']:.3f}  {r['volume']:>6}  {r['keyword']}  [{r['tier']}]" + (f"  ! {r['head_word_of_other_page']}" if r["head_word_of_other_page"] else ""))
    print(f"\n2) семантичні слова (є у >= {cfg['term_min_competitors']} конкурентів): {len(b_rows)}")
    for r in b_rows:
        print(f"  {r['competitors']:>2}/{N}  {r['sim_best']:.2f}  {r['term']}" + (f"  [анкор: {r['head_word_of_other_page']}]" if r["head_word_of_other_page"] else ""))
    gaps = [r for r in c_rows if r["gap"]]
    print(f"\n3) заголовків: {len(heads)}, підтем із >=2 конкурентами: {sum(r['competitors'] >= 2 for r in c_rows)}, прогалин: {len(gaps)}")
    for r in c_rows:
        if r["competitors"] >= 2:
            print(f"  {r['competitors']:>2}/{N}  {'ПРОГАЛИНА ' if r['gap'] else ''}«{r['subtopic']}» | на власній: {r['own_status']} | слова: {', '.join(r['topic_words'])}"
                  f"\n         " + " | ".join(r["headings"][:7])[:330])
    print("saved", ctx["f"]["embeddings"])


if __name__ == "__main__":
    main()
