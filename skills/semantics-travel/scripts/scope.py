#!/usr/bin/env python3
"""semantics-travel / scope: boundary of a collection. Every keyword is labelled
  core     (ядро)     = contains a word of `scope_terms` (CLAUDE.md of the direction, mandatory) - the topic itself, its modifiers
                        (price, buy, all inclusive, departure city, year, season...), its regions and tour types («ägypten urlaub hurghada»,
                        «ägypten last minute»): clustered and distributed, the matrix region x tour type works on them
  adjacent (суміжне)  = NOT clustered, NOT distributed, only the sheet «Напрямки розширення»:
                        - «поза межами збору»: no word of scope_terms in the keyword (a resort without the country, another country...)
                        - «суміжне»: a word of scope_terms + a product the site does not sell (profile: "sells": false)
  junk     (сміття)   = weather, visa, news, maps, competitor brands, irrelevant.
All other words come from the market profile (profiles/<code>.json, key "scope") and the regions of CLAUDE.md / profile destinations,
so nothing market-specific lives in this file.  Pure functions, no API.
"""
import collections, re

CORE, ADJ, JUNK = "core", "adjacent", "junk"
OUT_MARK, ADJ_MARK = "поза межами збору", "суміжне"
OUT_REASON = "поза межами збору (немає слова теми зі scope_terms)"


def scope_regex(S):
    """scope_terms of the direction: words/regexes split by |, case-insensitive substring match."""
    return re.compile("|".join(S["scope_terms"]), re.I)


class Scope:
    def __init__(self, P, R, S):
        sc = P.get("scope", {})
        self.products = {k: dict(v, _m=re.compile(v["match"], re.I), _x=re.compile(v["exclude"], re.I) if v.get("exclude") else None)
                         for k, v in sc.get("products", {}).items()}
        self.junk = [(n, re.compile(rx, re.I)) for n, rx in sc.get("junk", {}).items()]
        self.regions = collections.OrderedDict(R.REGIONS)
        self.country = S.country.lower()
        self.scope_rx = scope_regex(S)
        # a product that the page itself is about is NOT adjacent (CLAUDE.md `core_products: pauschalreise|all inclusive`; default: none)
        self.core_products = {x for x in re.split(r"\|", S.get("core_products", "")) if x}

    districts = ()

    def region_of(self, kl):
        for d in self.districts:
            if re.search(r"(?<![a-z])" + re.escape(d.lower()) + r"(?![a-z])", kl):
                return d
        for name, pat in self.regions.items():
            if re.search(pat, kl):
                return name
        return None

    def product_of(self, kl):
        for key, p in self.products.items():
            if key in self.core_products:
                continue
            if p["_m"].search(kl) and not (p["_x"] and p["_x"].search(kl)):
                return key
        return None

    def in_scope(self, keyword):
        return bool(self.scope_rx.search(keyword.lower()))

    def theme_of(self, kl):
        """Direction named in the keyword (region and/or another product), "" when none."""
        reg, prod = self.region_of(kl), self.product_of(kl)
        if reg and prod:
            return f"{reg.title()} + {self.products[prod]['name']}"
        return reg.title() if reg else self.products[prod]["name"] if prod else ""

    def label(self, keyword):
        """-> (label, theme, reason). theme is the extension direction for adjacent keywords; reason starts with OUT_MARK or ADJ_MARK."""
        kl = keyword.lower()
        for name, rx in self.junk:
            if rx.search(kl):
                return JUNK, name, f"сміття: {name}"
        if not self.in_scope(kl):
            return ADJ, self.theme_of(kl) or "інше (без слова теми)", OUT_REASON
        prod = self.product_of(kl)
        if prod and not self.products[prod].get("sells", True):
            return ADJ, self.theme_of(kl), "суміжне: продукт, який сайт не продає"
        return CORE, "", "ядро"

    def themes(self, items, existing_pages=(), region_pages=None):
        """items: [{keyword, volume}] adjacent -> rows for sheet «Напрямки розширення»."""
        g = collections.defaultdict(list)
        for it in items:
            g[(it.get("_mark", ""), it["_theme"])].append(it)
        rows = []
        for (mark, theme), ks in sorted(g.items(), key=lambda kv: -sum(x["volume"] for x in kv[1])):
            ks.sort(key=lambda x: -x["volume"])
            vol = sum(x["volume"] for x in ks)
            rows.append({"theme": theme, "mark": mark, "n": len(ks), "volume": vol, "examples": ", ".join(f"{x['keyword']} ({x['volume']})" for x in ks[:5]),
                         "kind": ks[0].get("_kind"), "items": ks})
        return rows


def recommend(row, products, existing_pages, region_pages, parent_page=""):
    """Recommendation text: окрема сторінка / режим extend-region / ігнорувати."""
    th = row["theme"]
    low = th.lower()
    if row.get("mark") == OUT_MARK:
        if row["volume"] < 300:
            return "поза межами збору: малий обсяг, ігнорувати поки що"
        return "поза межами збору: окремий збір у своїй папці зі своїм scope_terms (курорт/тема), якщо напрямок потрібен"
    if any(low.split(" + ")[0] == r.lower() for r in region_pages or []):
        return "вже виділено окрему сторінку регіону; ключі матриці ведуть на неї"
    nows = [i.get("_now", "") for i in row["items"]]
    dom = max(set(nows), key=nows.count) if nows else ""
    if dom and dom != parent_page and not dom.startswith("—"):
        return f"вже є окрема сторінка/матриця: {dom} ({'існує' if dom in existing_pages else 'рекомендована'})"
    prod = next((p for p in products.values() if p["name"] == th.split(" + ")[-1]), None)
    is_region = prod is None or " + " in th
    if prod is not None and not prod.get("sells", True):
        return "ігнорувати (продукт, який сайт не продає)" if row["volume"] < 500 else "ігнорувати або окремий проєкт (продукт поза асортиментом сайту)"
    if is_region and row["volume"] >= 300:
        return "режим extend-region (зібрати попит району й виділити окрему сторінку)"
    if row["volume"] >= 300:
        return "окрема сторінка"
    return "ігнорувати поки що (малий обсяг) або додати блоком на батьківську сторінку"
