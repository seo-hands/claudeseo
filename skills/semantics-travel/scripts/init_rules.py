#!/usr/bin/env python3
"""semantics-travel / init_rules: copy the rules engine (presets/travel.py) to <workdir>/semantics-rules.py so the LOGIC of this project can be edited.

python init_rules.py [--workdir .] [--force]
analyze.py and the other scripts prefer <workdir>/semantics-rules.py over presets/<preset>.py.  Edit there: lemma clusters (lemma_key, CLUSTERS),
landing-page classification (PATH_RULES, TITLE_RULES, INFO_DOMAINS, TOUR_DOMAINS, HUB_COUNTRY), page mapping (page_for, SLUG, FAM_*), token lists.
Language/country words are NOT here: they live in scripts/profiles/<code>.json (override per project in semantics-profile.json).
"""
import argparse, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_common as C


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--claude-md")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    S = C.load_settings(a.workdir, a.claude_md)
    dst = os.path.join(a.workdir, "semantics-rules.py")
    if os.path.exists(dst) and not a.force:
        sys.exit("semantics-rules.py вже існує (--force щоб перезаписати)")
    shutil.copy(os.path.join(C.SKILL_DIR, "presets", S.preset + ".py"), dst)
    print("створено", dst)


if __name__ == "__main__":
    main()
