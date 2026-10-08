#!/usr/bin/env python3
"""Stage 2, step 5: semantic similarity with a local open embedding model (free, no API).

python scripts/embed_terms.py

Input: competitors-turkei.json.  Output: embeddings-turkei.json
 (a) hub keywords vs main / adjacent keywords, tiers 0.80 / 0.65
 (b) meaningful terms from competitor texts: doc frequency >= 3 and similarity >= 0.60
 (c) H2/H3 of competitors clustered at >= 0.75 into subtopics; gaps = in >= 5 competitors and absent on the own page
Similarity comes from an open model, not from Google: a hint next to volume and TOP analysis, not a replacement.
"""
import json, os, re, sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "competitors-turkei.json")
OUT = os.path.join(ROOT, "embeddings-turkei.json")
MODEL = "jinaai/jina-embeddings-v2-base-de"
CORE, MID, TERM_SIM, TERM_DF, TOPIC_SIM, GAP_DF = 0.80, 0.65, 0.60, 3, 0.75, 5

STOP = set("""aber alle allem allen aller alles als also am an ander andere anderem anderen anderer anderes auch auf aus bei beim bin bis bist
da dabei dafür damit dann das dass dazu dein deine deinem deinen deiner dem den denn der des dessen dich die dies diese diesem diesen dieser
dieses dir doch dort du durch ein eine einem einen einer eines einige er es etwas euch euer eure für gegen gibt hat hatte haben hier hin
ich ihm ihn ihnen ihr ihre ihrem ihren ihrer im in ins ist ja jede jedem jeden jeder jedes jetzt kann kein keine keinem keinen können könnt
lässt man mehr mein meine mich mir mit muss nach nicht nichts noch nur ob oder ohne sehr sein seine seinem seinen seiner seit sich sie sind
so sowie sowohl über um und uns unser unsere unserem unseren unserer unter viel viele vom von vor war waren was weil weiter welche welcher
wenn wer werden wie wieder wir wird wo wurde zu zum zur zwischen ab bzw etc ca inkl pro je per bietet bieten finden findest findet
sie ihnen ihre gut ganz besonders zudem dabei hierbei dank egal natürlich außerdem ebenfalls bereits immer oft gerne gern rund
lassen lässt machen macht geht gehen gilt liegt liegen kommen kommt sollte sollten möchte möchten möchtest kannst wer's
uhr montag dienstag mittwoch donnerstag freitag samstag sonntag feiertag www http https de com""".split())
# navigation / brand / consent vocabulary that is not page semantics
NAV = set("""cookie cookies datenschutz impressum agb newsletter anmelden login registrieren passwort hotline service kontakt
gutschein cashback testsieger check24 lidl aldi anex sonnenklar neckermann restplatzbörse restplatzboerse holidayplatz oeger öger
schauinsland travelantis hansemerkur ekomi tüv berge mehr anzeigen weitere laden informationen öffnen profilfoto caroline kupfer carolin
gersin euvia travel gmbh dtgv verbraucherstudien bewertungen kundenbewertungen image html banner""".split())
OTHER_PAGES = {"last minute": "/tour/turkei/last-minute", "last-minute": "/tour/turkei/last-minute", "lastminute": "/tour/turkei/last-minute",
               "pauschalreise": "/tour/turkei/pauschalreise", "pauschalurlaub": "/tour/turkei/pauschalreise",
               "all inclusive": "/tour/turkei/all-inclusive", "all-inclusive": "/tour/turkei/all-inclusive",
               "hotel": None}
ENTITIES = ["Antalya", "Side", "Alanya", "Belek", "Kemer", "Lara", "Bodrum", "Marmaris", "Fethiye", "Dalaman", "Izmir", "Kusadasi", "Didim",
            "Cesme", "Istanbul", "Kappadokien", "Pamukkale", "Ephesos", "Ephesus", "Ölüdeniz", "Dalyan", "Türkische Riviera", "Türkische Ägäis",
            "Lykische Küste", "Taurusgebirge", "Mittelmeer", "Ägäis", "Bosporus", "Hagia Sophia", "Blaue Moschee", "Aspendos", "Perge", "Troja",
            "Konyaalti", "Kleopatra Strand", "Manavgat", "Türkische Lira", "Schwarzes Meer", "Schwarzmeerküste"]
TOK = re.compile(r"[A-Za-zÄÖÜäöüßğışçİ][A-Za-zÄÖÜäöüßğışçİ\-]*[A-Za-zÄÖÜäöüßğışçİ]|\d{4}")


def clean_text(c):
    """main text of a competitor without heading lines that are just hotel names / UI"""
    return "\n".join(l[3:] if l.startswith("## ") else l for l in c["main_text"].split("\n") if l.strip())


def ok_edge(t):
    return t.lower() not in STOP and t.lower() not in NAV and len(t) > 2


def terms_of(text):
    """unigram nouns (capitalised in German), 2-3-grams around a noun, known entities"""
    out = {}
    for sent in re.split(r"(?<=[.!?:])\s+|\n+|[•|–—]", text):
        toks = TOK.findall(sent)
        for i, t in enumerate(toks):
            cap = t[0].isupper()
            # a capitalised word at sentence start may be a non-noun: accept only if it occurs capitalised elsewhere (checked later via counts)
            if cap and ok_edge(t) and len(t) >= 4 and not t.isdigit():
                out.setdefault(t.lower(), []).append((t, i == 0))
            for n in (2, 3):
                g = toks[i:i + n]
                if len(g) < n or not ok_edge(g[0]) or not ok_edge(g[-1]):
                    continue
                if any(x.lower() in NAV for x in g) or not any(x[0].isupper() and x.lower() not in STOP for x in g[(1 if i == 0 else 0):] or g):
                    continue
                if n == 3 and g[1].lower() in STOP and g[1].lower() not in ("in", "der", "die", "das", "und", "für", "am", "an", "mit", "im", "zur", "zum"):
                    continue
                out.setdefault(" ".join(x.lower() for x in g), []).append((" ".join(g), False))
    low = text.lower()
    for e in ENTITIES:
        if re.search(r"(?<!\w)" + re.escape(e.lower()) + r"(?!\w)", low):
            out.setdefault(e.lower(), []).append((e, False))
    return out


def cos(a, b):
    return a @ b.T


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    comps = [c for c in data["competitors"] if c.get("ok")]
    own = data["own"]
    main_kw, adjacent = data["main_keyword"], data["adjacent"]
    refs = [main_kw] + adjacent
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name=MODEL)
    except Exception as e:  # never substitute the model silently
        print(f"MODEL LOAD FAILED: {MODEL}: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

    def embed(texts):
        v = np.array(list(model.embed(list(texts), batch_size=64)), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    R = embed(refs)

    # (a) hub keywords
    kws = data["hub_keywords"]
    K = embed([k["keyword"] for k in kws])
    S = cos(K, R)
    a_rows = []
    for k, s in zip(kws, S):
        sm = float(s[0])
        adj = {adjacent[i]: round(float(s[i + 1]), 3) for i in range(len(adjacent))}
        best_adj = max(adj, key=adj.get)
        a_rows.append({"keyword": k["keyword"], "translation": k["translation"], "volume": k["volume"], "sim_main": round(sm, 3),
                       "sim_adjacent": adj, "closest_adjacent": best_adj, "sim_closest_adjacent": adj[best_adj],
                       "tier": "ядро" if sm >= CORE else ("H2/текст" if sm >= MID else "FAQ/довгий хвіст")})
    a_rows.sort(key=lambda r: -r["sim_main"])

    # (b) terms from competitor texts
    df, forms, tf = Counter(), defaultdict(Counter), Counter()
    for c in comps:
        t = terms_of(clean_text(c))
        for k, occ in t.items():
            non_initial = [f for f, first in occ if not first]
            if " " not in k and not non_initial and len(occ) < 2:
                continue  # only seen once as a sentence-initial capitalised word: probably not a noun
            df[k] += 1
            tf[k] += len(occ)
            for f, _ in occ:
                forms[k][f] += 1
    cand = [k for k, n in df.items() if n >= TERM_DF]
    # light merge of inflected variants (Strand/Strände are kept apart; only -s/-n/-en/-e/-es endings are merged)
    merged = {}
    for k in sorted(cand, key=lambda x: (-df[x], len(x))):
        base = next((m for m in merged if " " not in k and " " not in m and k != m and k.startswith(m) and k[len(m):] in ("s", "n", "en", "e", "es", "er")), None)
        if base:
            merged[base]["variants"].append(k)
        else:
            merged[k] = {"variants": []}
    cand = list(merged)
    # drop a shorter term that only ever lives inside a longer candidate with the same doc frequency
    longer = [k for k in cand if " " in k]
    cand = [k for k in cand if not any(k != l and re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", l) and df[l] >= df[k] for l in longer)]
    T = embed([forms[k].most_common(1)[0][0] for k in cand])
    ST = cos(T, R)
    b_rows, b_low = [], []
    for k, s in zip(cand, ST):
        best = int(np.argmax(s))
        if float(s[best]) < TERM_SIM:
            b_low.append({"term": forms[k].most_common(1)[0][0], "df": df[k], "of": len(comps), "tf": tf[k], "sim_main": round(float(s[0]), 3),
                          "sim_best": round(float(s[best]), 3), "variants": merged[k]["variants"],
                          "is_other_page_key": any(re.search(r"(?<!\w)" + re.escape(w), k) for w in OTHER_PAGES)})
            continue
        form = forms[k].most_common(1)[0][0]
        other = next((p for w, p in OTHER_PAGES.items() if re.search(r"(?<!\w)" + re.escape(w), k)), "-")
        b_rows.append({"term": form, "df": df[k], "of": len(comps), "tf": tf[k], "variants": merged[k]["variants"],
                       "sim_main": round(float(s[0]), 3), "sim_best": round(float(s[best]), 3), "closest_ref": refs[best],
                       "kind": "сутність" if k in [e.lower() for e in ENTITIES] else ("слово" if " " not in k else f"{len(k.split())}-грама"),
                       "other_page_key": other if other != "-" else None, "is_other_page_key": other != "-"})
    b_rows.sort(key=lambda r: (-r["df"], -r["sim_best"]))

    # (c) subtopics from H2/H3
    heads = []
    for c in comps:
        host = urlparse(c["url"]).netloc.replace("www.", "")
        seen = set()
        for o in c["outline"]:
            t = o["text"].strip()
            if len(t) < 4 or t.lower() in seen:
                continue
            seen.add(t.lower())
            heads.append({"host": host, "level": o["level"], "text": t})
    H = embed([h["text"] for h in heads])
    # agglomerative clustering, average linkage, merge while the best pair similarity >= TOPIC_SIM
    clusters = [[i] for i in range(len(heads))]
    SIM = cos(H, H)
    while True:
        best, bi, bj = -1, -1, -1
        cents = np.array([H[c].mean(axis=0) for c in clusters])
        cents /= np.linalg.norm(cents, axis=1, keepdims=True)
        CS = cents @ cents.T
        np.fill_diagonal(CS, -1)
        # average linkage evaluated on the best centroid pairs only (cheap and close enough for ~200 headings)
        for i, j in zip(*np.unravel_index(np.argsort(-CS, axis=None)[:40], CS.shape)):
            if i >= j:
                continue
            avg = float(SIM[np.ix_(clusters[i], clusters[j])].mean())
            if avg > best:
                best, bi, bj = avg, i, j
        if best < TOPIC_SIM:
            break
        clusters[bi] += clusters[bj]
        del clusters[bj]
    own_heads = [o["text"] for o in own.get("outline", [])]  # H1 is the page topic, not a subtopic: it would "cover" every heading with «Türkei Urlaub»
    OH = embed(own_heads) if own_heads else np.zeros((0, H.shape[1]), dtype=np.float32)
    c_rows = []
    for cl in clusters:
        hosts = sorted({heads[i]["host"] for i in cl})
        cent = H[cl].mean(axis=0)
        cent /= np.linalg.norm(cent)
        label = heads[cl[int(np.argmax(H[cl] @ cent))]]["text"]
        own_sim, own_match = 0.0, None
        if len(OH):
            m = OH @ H[cl].T
            j = int(np.argmax(m.max(axis=1)))
            own_sim, own_match = float(m.max()), own_heads[j]
        on_own = own_sim >= TOPIC_SIM
        c_rows.append({"subtopic": label, "competitors": len(hosts), "of": len(comps), "hosts": hosts,
                       "headings": [f"{heads[i]['host']}: {heads[i]['text']}" for i in cl],
                       "sim_main": round(float(cent @ R[0]), 3), "own_best_sim": round(own_sim, 3), "own_best_heading": own_match,
                       "on_own_page": on_own, "gap": len(hosts) >= GAP_DF and not on_own})
    c_rows.sort(key=lambda r: (-r["competitors"], -len(r["headings"])))

    out = {"model": MODEL, "note": "Близькість рахує відкрита модель, а не Google: орієнтир поруч із частотністю й аналізом ТОП, а не замість них.",
           "thresholds": {"core": CORE, "mid": MID, "term_sim": TERM_SIM, "term_df": TERM_DF, "topic_sim": TOPIC_SIM, "gap_df": GAP_DF},
           "references": refs, "competitors_used": [c["url"] for c in comps],
           "keywords": a_rows, "terms": b_rows, "terms_candidates_df3": len(cand),
           "terms_below_threshold": sorted(b_low, key=lambda r: (-r["df"], -r["sim_best"])),
           "subtopic_singleton_list": [r for r in c_rows if r["competitors"] < 2],
           "subtopics": [r for r in c_rows if r["competitors"] >= 2], "subtopic_singletons": sum(r["competitors"] < 2 for r in c_rows),
           "headings_total": len(heads), "own_headings": own_heads}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("model:", MODEL, "| competitors:", len(comps))
    print("\n(a) keywords:", Counter(r["tier"] for r in a_rows))
    for r in a_rows:
        print(f"  {r['sim_main']:.3f}  adj {r['sim_closest_adjacent']:.3f}  {r['volume']:>6}  {r['keyword']}  [{r['tier']}]")
    print(f"\n(b) terms: candidates df>={TERM_DF}: {len(cand)}, kept sim>={TERM_SIM}: {len(b_rows)}")
    for r in b_rows[:150]:
        print(f"  {r['df']:>2}/{r['of']}  {r['sim_best']:.3f}  {r['term']}  ({r['kind']}){' [ключ іншої сторінки]' if r['is_other_page_key'] else ''}")
    print(f"\n(c) headings: {len(heads)}, clusters with >=2 competitors: {sum(r['competitors'] >= 2 for r in c_rows)}, gaps: {sum(r['gap'] for r in c_rows)}")
    for r in c_rows:
        if r["competitors"] >= 2:
            print(f"  {r['competitors']:>2}/{r['of']}  own={r['own_best_sim']:.2f} {'GAP ' if r['gap'] else ''}{r['subtopic']}  <- " + " | ".join(r["headings"][:8])[:400])
    print("\nbelow threshold:")
    for r in sorted(b_low, key=lambda r: (-r["df"], -r["sim_best"])):
        print(f"  {r['df']:>2}  {r['sim_best']:.3f}  {r['term']}  {r['variants'] or ''}")
    print("\nsingletons:")
    for r in c_rows:
        if r["competitors"] < 2:
            print("  ", " | ".join(r["headings"])[:200])
    print("saved", OUT)


if __name__ == "__main__":
    main()
