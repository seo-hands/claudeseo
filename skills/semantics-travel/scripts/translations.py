#!/usr/bin/env python3
"""semantics-travel / translations: Ukrainian translations of keywords stored in keywords.json (translation_uk, translation_note_uk).

The translation itself is done by Claude (own translation by meaning and search intent, not word for word; no machine services).
python translations.py [--workdir .] missing [--out translations-todo.json]   list keywords without translation (to translate)
python translations.py [--workdir .] apply translations.json [--force]       merge {"keyword": ["переклад", "примітка або порожньо"]}
python translations.py [--workdir .] check                                    count translated / missing (including region keywords)

Rules for the translator: Reise/Urlaub -> подорож/відпочинок, Pauschalreise -> пакетний тур (переліт + готель), last minute -> гарячі тури,
all inclusive -> «все включено», Rundreise -> екскурсійний тур, Reisewarnung -> попередження щодо подорожей; toponyms in Ukrainian
(Анталія, Сіде, Каппадокія, Лара); natural Ukrainian without calques ("по Туреччині" -> "до Туреччини", "у Туреччині");
a short note only for colloquial forms, typos or ambiguous words.  Already translated keywords are never translated again.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("cmd", choices=["missing", "apply", "check"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out", default="translations-todo.json")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    p = os.path.join(a.workdir, "keywords.json")
    d = json.load(open(p, encoding="utf-8"))
    miss = [k for k in d["keywords"] if not k.get("translation_uk")]
    if a.cmd == "check":
        print(f"перекладено {len(d['keywords']) - len(miss)} з {len(d['keywords'])}; без перекладу {len(miss)}")
    elif a.cmd == "missing":
        todo = [{"keyword": k["keyword"], "volume": k["volume"]} for k in miss]
        json.dump(todo, open(os.path.join(a.workdir, a.out), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(todo)} ключів без перекладу -> {a.out}")
    else:
        tr = json.load(open(a.file, encoding="utf-8"))
        n = 0
        for k in d["keywords"]:
            if k["keyword"] in tr and (a.force or not k.get("translation_uk")):
                v = tr[k["keyword"]]
                k["translation_uk"], k["translation_note_uk"] = (v[0], v[1] if len(v) > 1 else "") if isinstance(v, list) else (v, "")
                n += 1
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        left = [k["keyword"] for k in d["keywords"] if not k.get("translation_uk")]
        print(f"застосовано {n}; лишилось без перекладу {len(left)}", left[:5])


if __name__ == "__main__":
    main()
