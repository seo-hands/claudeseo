#!/usr/bin/env python3
"""semantics-travel / scope: topic boundaries of a page. Every keyword is labelled
  core     (ядро)     = page topic + modifiers (price, buy, all inclusive, departure city, year, season, for two, with kids...)
  adjacent (суміжне)  = same country, but ANOTHER region/district or ANOTHER product (hot tours, hotels, flights, excursions...)
  junk     (сміття)   = weather, visa, news, maps, competitor brands, irrelevant.
All words come from the market profile (profiles/<code>.json, key "scope") and the regions of CLAUDE.md / profile destinations,
so nothing market-specific lives in this file.  Pure functions, no API.
"""
import collections, re

CORE, ADJ, JUNK = "core", "adjacent", "junk"


class Scope:
    def __init__(self, P, R, S):
        sc = P.get("scope", {})
        self.products = {k: dict(v, _m=re.compile(v["match"], re.I), _x=re.compile(v["exclude"], re.I) if v.get("exclude") else None)
                         for k, v in sc.get("products", {}).items()}
        self.junk = [(n, re.compile(rx, re.I)) for n, rx in sc.get("junk", {}).items()]
        self.regions = collections.OrderedDict(R.REGIONS)
        self.country = S.country.lower()
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

    def label(self, keyword):
        """-> (label, theme, reason). theme is the extension direction for adjacent keywords."""
        kl = keyword.lower()
        for name, rx in self.junk:
            if rx.search(kl):
                return JUNK, name, f"сміття: {name}"
        reg, prod = self.region_of(kl), self.product_of(kl)
        if reg and prod:
            return ADJ, f"{reg.title()} + {self.products[prod]['name']}", "суміжне: район + інший продукт"
        if reg:
            return ADJ, f"{reg.title()}", "суміжне: район/регіон"
        if prod:
            return ADJ, self.products[prod]["name"], "суміжне: інший продукт"
        return CORE, "", "ядро"

    def themes(self, items, existing_pages=(), region_pages=None):
        """items: [{keyword, volume}] adjacent -> rows for sheet «Напрямки розширення»."""
        g = collections.defaultdict(list)
        for it in items:
            g[it["_theme"]].append(it)
        rows = []
        for theme, ks in sorted(g.items(), key=lambda kv: -sum(x["volume"] for x in kv[1])):
            ks.sort(key=lambda x: -x["volume"])
            vol = sum(x["volume"] for x in ks)
            rows.append({"theme": theme, "n": len(ks), "volume": vol, "examples": ", ".join(f"{x['keyword']} ({x['volume']})" for x in ks[:5]),
                         "kind": ks[0].get("_kind"), "items": ks})
        return rows


def recommend(row, products, existing_pages, region_pages, parent_page=""):
    """Recommendation text: окрема сторінка / режим extend-region / ігнорувати."""
    th = row["theme"]
    low = th.lower()
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
