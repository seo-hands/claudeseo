"""Preset travel: rules for tour/travel sites (tours, package tours, hotels, destinations).

The ENGINE only: everything that depends on the market language/country (words, regexes, domains, brands, resorts) is in
scripts/profiles/<code>.json (de.json ...) and is loaded by sp_common.load_profile().  A project can override single profile keys in
<workdir>/semantics-profile.json (dicts are merged, lists/scalars replaced) or copy this file to <workdir>/semantics-rules.py.
make(S) returns the namespace used by analyze.py and the other scripts.
"""
import collections, re
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import sp_common as C


def make(S):
    P = C.load_profile(S, S.get("_workdir", "."))
    page_base = S.page_base.rstrip("/")
    hotels_page = S.hotels_page or (page_base + "/hotels")
    country = S.country
    country_lc = re.escape(country.lower())

    # ---------------- regions: CLAUDE.md `region:` lines, else the profile's destination defaults ----------------
    REGIONS = collections.OrderedDict(S.regions)
    if not REGIONS:
        hubs = set(S.hub_slugs.split("|")) | {S.slug}
        for dest, v in P.get("destinations", {}).items():
            if dest in hubs:
                REGIONS.update(v.get("regions", {}))
    lemma_regions = [x for x in re.split(r"\|", S.lemma_regions) if x] or list(REGIONS)

    def detect_region(text):
        for name, pat in REGIONS.items():
            if re.search(pat, text):
                return name
        return None

    # ---------------- lemma clusters ----------------
    mods = P["modifiers"]
    sub_vars = {"{price}": "|".join(mods["price"]), "{months}": "|".join(mods["months"])}

    def expand(rx):
        for a, b in sub_vars.items():
            rx = rx.replace(a, b)
        return rx

    CLUSTERS = {k: (v[0].replace("{country}", country), v[1]) for k, v in P["cluster_names"].items()}
    for r in REGIONS:
        CLUSTERS["region_" + r] = (f"Регіон: {r.title()}", None)

    def _match(rule, t):
        if rule.get("default") or not any(x in rule for x in ("match", "startswith", "region")):
            return True
        if "startswith" in rule:
            return t.startswith(rule["startswith"])
        if "region" in rule:
            return bool(detect_region(t))
        ok = bool(re.search(expand(rule["match"]), t))
        return ok and not (rule.get("not") and re.search(rule["not"], t))

    def lemma_key(k):
        """Lemma/intent cluster of a keyword (first matching rule of the profile wins; regions first)."""
        t = k.lower().replace("-", " ")
        for r in lemma_regions:
            if r in REGIONS and re.search(REGIONS[r], t):
                return "region_" + r
        for rule in P["lemma_rules"]:
            if _match(rule, t):
                if rule.get("sub"):
                    for s in rule["sub"]:
                        if _match(s, t):
                            return s["key"]
                return rule["key"]
        return "urlaub_core"

    # ---------------- classification of competitor landing pages ----------------
    L = P["landing"]
    INFO_DOMAINS, TOUR_DOMAINS = L["info_domains"], L["tour_domains"]
    PATH_RULES = [(t, rx) for t, rx in L["path_rules"]]
    TITLE_RULES = [(t, rx.replace("{country_lc}", country_lc)) for t, rx in L["title_rules"]]
    slugs = S.hub_slugs
    roots = L["hub_roots"]
    HUB_COUNTRY = re.compile(r"/(" + roots + r")(/[a-z0-9-]+)*/(" + slugs + r")(/\d+)?(\.html|\.php)?/?$"
                             r"|/(" + slugs + r")(/(" + slugs + r"))?(\.html|\.php)?/?$" + (("|" + S.hub_extra_regex) if S.hub_extra_regex else ""))
    TYPE_LABEL = {
        ("hub_country", False): "хаб країни", ("hub_region", True): "хаб регіону",
        ("lastminute", False): "last minute (країна)", ("lastminute", True): "last minute (регіон)",
        ("allinclusive", False): "all inclusive (країна)", ("allinclusive", True): "all inclusive (регіон)",
        ("pauschal", False): "pauschalreise (країна)", ("pauschal", True): "pauschalreise (регіон)",
        ("hotel", False): "готель", ("hotel", True): "готель (регіон)", ("info", False): "інформаційна",
        ("rundreise", False): "rundreise", ("fruehbucher", False): "Frühbucher", ("other", False): "інше",
    }

    def type_label(typ, region):
        return TYPE_LABEL.get((typ, bool(region))) or TYPE_LABEL.get((typ, False)) or typ

    def classify_url(url, title=""):
        """-> (type, region).  Types: hub_country, hub_region, lastminute, allinclusive, pauschal, hotel, info, rundreise, fruehbucher, other."""
        u = urlsplit(url)
        host, path, t = u.netloc.lower(), unquote(u.path).lower(), title.lower()
        if re.search(INFO_DOMAINS, host + path):
            return "info", None
        if re.search(TOUR_DOMAINS, host):
            return "rundreise", None
        region = detect_region(path)
        typ = next((name for name, pat in PATH_RULES if re.search(pat, path)), None)
        if typ is None:
            typ = next((name for name, pat in TITLE_RULES if re.search(pat, t)), None)
            if typ == "hotel" and len([s for s in path.split("/") if s]) < 3:
                typ = None
        if typ == "hub_listing":                     # operator offer lists ("Flug+Hotel", place pages) are hubs, not hotel pages
            return ("hub_region", region) if region else ("hub_country", None)
        if typ == "hotel":
            region = detect_region(path + " " + t)
        if typ:
            return typ, region
        if region:
            return "hub_region", region
        if HUB_COUNTRY.search(path):
            return "hub_country", None
        return "other", None

    # ---------------- candidate pages of the site ----------------
    SLUG = dict(P["page_slugs"])
    INFO_SLUGS = {SLUG["info_hinweise"], SLUG["info_zeit"], SLUG["info_ratgeber"]}

    def page_for(typ, region, kwreg=None, topic=None):
        """Candidate landing page for a competitor page type (None = no page).  kwreg = region named in the keyword."""
        topic = topic or SLUG["info_hinweise"]
        r = f"{page_base}/{region}" if region else None
        if typ == "hub_country":
            return page_base
        if typ == "hub_region":
            return r
        if typ == "lastminute":
            return (r + "/" + SLUG["lastminute"]) if r else f"{page_base}/{SLUG['lastminute']}"
        if typ == "fruehbucher":
            return f"{page_base}/{SLUG['lastminute']}"          # last-minute and early-booking pages count together
        if typ == "allinclusive":
            return (r + "/" + SLUG["allinclusive"]) if r else f"{page_base}/{SLUG['allinclusive']}"
        if typ == "pauschal":
            return (r + "/" + SLUG["pauschal"]) if r else f"{page_base}/{SLUG['pauschal']}"
        if typ == "hotel":
            return r if (r and region == kwreg) else hotels_page
        if typ == "info":
            return f"{page_base}/{topic}"
        if typ == "rundreise":
            return f"{page_base}/{SLUG['rundreise']}"
        return None

    FAM_BY_LAST = {SLUG["lastminute"]: "lastminute", SLUG["allinclusive"]: "allinclusive", SLUG["pauschal"]: "pauschal", SLUG["rundreise"]: "rundreise"}
    FAM_BY_LAST.update({s: "info" for s in INFO_SLUGS})
    FAM_PRIORITY = ["hub", "lastminute", "allinclusive", "pauschal", "info", "hotel", "rundreise"]
    FAM_COUNTRY_PAGE = {f: f"{page_base}/{SLUG[f]}" for f in ("lastminute", "allinclusive", "pauschal")}
    FAM_SUFFIX = {f: SLUG[f] for f in ("lastminute", "allinclusive", "pauschal")}
    ROOT_PAGE_FOR = {"rundreise": f"{page_base}/{SLUG['rundreise']}"}

    def family(page):
        if page == hotels_page:
            return "hotel"
        return FAM_BY_LAST.get(page.rsplit("/", 1)[1], "hub")

    def parent_page(page, kwreg=None):
        """Broader page when no separate page is justified."""
        if page == page_base:
            return page
        return f"{page_base}/{kwreg}" if kwreg else page_base

    def keyword_family(k):
        """Product family named in the keyword (a verdict about a page type applies only to keywords of that family)."""
        t = k.lower()
        for r in P["keyword_family"]:
            if ("startswith" in r and t.startswith(r["startswith"])) or ("match" in r and re.search(r["match"], t)):
                return r["family"]
        return "hub"

    def topic_for(k):
        lk = lemma_key(k)
        T = P["topic"]
        return SLUG["info_zeit"] if lk in T["season_keys"] else SLUG["info_hinweise"] if lk.startswith(T["info_prefix"]) else SLUG["info_ratgeber"]

    N = {a: b.replace("{country}", country) for a, b in P["notes"].items()}
    GENERIC_NOTES = {page_base: N["hub"], f"{page_base}/{SLUG['info_hinweise']}": N["info_hinweise"], f"{page_base}/{SLUG['info_zeit']}": N["info_zeit"],
                     f"{page_base}/{SLUG['info_ratgeber']}": N["info_ratgeber"], f"{page_base}/{SLUG['rundreise']}": N["rundreise"],
                     f"{page_base}/{SLUG['pauschal']}": N["pauschal"], hotels_page: N["hotels"]}

    # ---------------- language helpers (dedupe, region extension, brand filter) ----------------
    T = P["tokens"]
    STOP, PLURAL = set(T["stop"]), dict(T["plural"])
    GENERIC_TOKENS, INFO_TOKENS = set(T["generic"]), set(T["info"])
    HOTEL_LIST_TOKENS, BRAND_NOISE, REGION_SEED_WORD = set(T["hotel_list"]), set(T["brand_noise"]), T["region_seed_word"]
    STOP_BRANDS = list(P.get("stop_brands", []))

    return SimpleNamespace(**{k: v for k, v in locals().items() if not k.startswith("_") and k not in ("S", "make", "P", "C")})
