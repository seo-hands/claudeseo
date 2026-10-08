#!/usr/bin/env python3
"""Rules of the backlinks-check skill as code: flags, verdict_auto, priority.  The text version is references/rules.md -
change both together.  Thresholds are starting values calibrated on the runs of 2026-10-08 (Ukraine, Kazakhstan)."""
import bl_common as bl

SPAM_MINUS = 40            # spam score above this is a minus (15-35 is neutral, up to 15 is good)
DOFOLLOW_MIN = 200         # fewer dofollow referring domains = weak profile
REL_TREND_MINUS = -20      # percentage points below the median of the list
CASINO_SERP_EXCLUDE = 7    # of 10 results for "casino OR bets" being casino reviews -> do not take
RISKY_SHARE_MINUS = 0.30   # share of risky niches among the latest materials of the advertising section
SPIKE_RATIO = 1.5          # dofollow donors grew 1.5x within 3 months
EXT_OUTLIER = 3            # external links per page above 3 medians of the list
CASINO_KW_SHARE = 0.05     # a casino-brand keyword gives at least 5 % of the top-100 traffic
LINK_PENALTY = 1.5         # an existing link to the acceptor multiplies the price per 1K when sorting
STRONGER = 1.1             # "noticeably stronger" for the 2-of-3 rule

HARD_WEAK = {"near_zero"}
EXCLUDE = {"casino_serp", "casino_home_sitewide"}
INFO = {"links_to_acceptor", "unverified_403", "serp_undetermined"}   # shown, but not counted as a minus


def stage1_flags(m, market, ext_median):
    F = []
    etv, thr = m["market_etv"], market["min_traffic"]
    if etv < thr / 10:
        F.append(("near_zero", f"трафіку ринку майже немає: {etv} візитів/міс (орієнтир {thr})"))
    elif etv < thr:
        F.append(("low_traffic", f"малий трафік ринку: {etv} візитів/міс (орієнтир {thr})"))
    if (m.get("spam") or 0) > SPAM_MINUS:
        F.append(("spam", f"spam score {m['spam']} (понад {SPAM_MINUS})"))
    if m.get("dofollow") is not None and m["dofollow"] < DOFOLLOW_MIN:
        F.append(("few_dofollow", f"лише {m['dofollow']} dofollow-донорів (менше {DOFOLLOW_MIN})"))
    if m.get("casino_pr", 0) >= CASINO_SERP_EXCLUDE:
        F.append(("casino_serp", f"{m['casino_pr']} з 10 результатів за «казино OR ставки» — PR казино"))
    if m.get("ext_per_page") and ext_median and m["ext_per_page"] > EXT_OUTLIER * ext_median:
        F.append(("ext_outlier", f"{m['ext_per_page']} вихідних на сторінку при медіані списку {ext_median}"))
    if m.get("links_to_acceptor"):
        F.append(("links_to_acceptor", "вже посилається на акцептор"))
    if any(v["state"] == "невизначено" for v in m["serp"].values()):
        F.append(("serp_undetermined", "частина SERP-запитів повернула сторонні сайти: «невизначено», не «чисто»"))
    return F


def stage2_flags(c, pages):
    """c - stage-2 data of a candidate, pages - parsed pages of the candidate (may be empty)."""
    F = []
    if c.get("traffic_rel") is not None and c["traffic_rel"] < REL_TREND_MINUS:
        F.append(("traffic_trend", f"трафік {c['traffic_change']:+.0f}% за рік, на {abs(c['traffic_rel']):.0f} п.п. гірше за медіану"))
    if c.get("dofollow_rel") is not None and c["dofollow_rel"] < REL_TREND_MINUS:
        F.append(("dofollow_trend", f"dofollow-донори {c['dofollow_change']:+.0f}% за рік, на {abs(c['dofollow_rel']):.0f} п.п. гірше за медіану"))
    if c.get("spike"):
        F.append(("donor_spike", f"стрибок dofollow-донорів: {c['spike'][0]} → {c['spike'][1]} за 3 місяці"))
    if c.get("casino_kw"):
        k = c["casino_kw"]
        F.append(("casino_keyword", f"запит «{k['keyword']}» дає {k['share'] * 100:.0f}% трафіку топ-100 ключів ({k['url']})"))
    home = (pages or {}).get("home") or {}
    risky_home = [r for r in home.get("risky") or [] if r["rel"] == "dofollow" and r["niche"] in bl.CFG["toxic_niches"]]
    if risky_home and home.get("sitewide"):
        F.append(("casino_home_sitewide", "наскрізні dofollow-посилання на казино: " + ", ".join(r["domain"] for r in risky_home)))
    elif risky_home:
        F.append(("casino_home", "dofollow-посилання на казино на головній (не наскрізні): " + ", ".join(r["domain"] for r in risky_home)))
    toxic = sorted({l["domain"] for a in (pages or {}).get("articles") or [] for l in a.get("body") or [] if l["niche"] in bl.CFG["toxic_niches"]})
    if toxic:
        F.append(("toxic_pr", "PR з посиланням на токсичну нішу: " + ", ".join(toxic)))
    lst = (pages or {}).get("listing") or {}
    if lst.get("items") and lst.get("risky_share") is not None and lst["risky_share"] >= RISKY_SHARE_MINUS:
        F.append(("risky_share", f"ризикові ніші — {lst['risky_share'] * 100:.0f}% останніх матеріалів рекламного розділу"))
    return F


def verdict_auto(flags, m, market, is_tld, notes):
    codes = {c for c, _ in flags}
    minus = len(codes - INFO)
    if codes & HARD_WEAK or codes & EXCLUDE or minus >= 3:
        return "слабкий"
    if minus == 0 and m["market_etv"] >= market["min_traffic"] and (is_tld or (notes or {}).get("travel_rubric")):
        return "сильний"
    return "середній"


def stronger_than(g, weakest):
    """The 2-of-3 rule for a domain outside the market TLD against the weakest market-TLD candidate."""
    if not weakest:
        return True
    wins = 0
    wins += (g.get("rank") or 0) > (weakest.get("rank") or 0) * STRONGER
    wins += (g.get("dofollow") or 0) > (weakest.get("dofollow") or 0) * STRONGER
    wins += (g.get("total_etv") or 0) > (weakest.get("market_etv") or 0) * STRONGER
    return wins >= 2


def price_key(m, is_tld):
    p = m.get("price_per_1k_market") if is_tld else m.get("price_per_1k_total")
    if p is None:
        return float("inf")
    return p * (LINK_PENALTY if m.get("links_to_acceptor") else 1)


def priority(doms, verdicts, excluded, candidates, market, n):
    """Order: verdict -> market TLD first -> price per 1K (market traffic for TLD domains, total traffic for the rest).
    Returns (ordered domains, {domain: recommendation}). Only stage-2 candidates can be recommended."""
    def key(d):
        m = doms[d]
        tld = bl.is_market_tld(d, market)
        return (1 if d in excluded else 0, 0 if d in candidates else 1, bl.VERDICTS.index(verdicts[d]), 0 if tld else 1, price_key(m, tld), d)
    order = sorted(doms, key=key)
    tld_c = [d for d in order if d in candidates and d not in excluded and bl.is_market_tld(d, market)]
    weakest = doms[tld_c[-1]] if tld_c else None
    rec, general, k, reserve = {}, 0, 0, False
    for d in order:
        tld = bl.is_market_tld(d, market)
        if d in excluded or d not in candidates:
            rec[d] = "не брати"
        elif k < n and (tld or (general < n // 2 and stronger_than(doms[d], weakest))):
            k += 1
            general += 0 if tld else 1
            rec[d] = f"РОЗМІСТИТИ #{k}"
        elif not reserve:
            reserve = True
            rec[d] = "резерв"
        else:
            rec[d] = "не брати"
    return order, rec


def candidates_auto(doms, market, n, notes):
    """N+1 candidates: market-TLD domains by market traffic, then other domains that pass the 2-of-3 rule (those with a
    travel rubric first), by total traffic."""
    ok = [d for d, m in doms.items() if "casino_serp" not in {c for c, _ in m["flags"]}]
    tld = sorted([d for d in ok if bl.is_market_tld(d, market)], key=lambda d: -doms[d]["market_etv"])
    weakest = doms[tld[-1]] if tld else None
    gen = [d for d in ok if d not in tld and stronger_than(doms[d], weakest)]
    gen.sort(key=lambda d: (0 if (notes.get(d) or {}).get("travel_rubric") else 1, -(doms[d].get("total_etv") or 0)))
    return (tld + gen)[: n + 1]
