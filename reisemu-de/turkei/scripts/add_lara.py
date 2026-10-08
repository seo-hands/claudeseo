#!/usr/bin/env python3
"""Add the Lara keywords (lara-demand.json) to keywords.json with groups and Ukrainian translations. No API calls.

python scripts/add_lara.py
Groups (lara_group): general -> /tour/turkei/antalya/lara; hotels_list -> same page (list of hotels);
weather_map -> same page, info block, low priority; hotel_name -> sheet "Готелі Lara" (single-hotel pages).
Excluded keywords go to keywords.json["filtered"] with a reason.  Keywords already in the main 78 are not duplicated.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = "«все включено»"
G = {  # general resort / holiday keywords
    "lara türkei": ("Лара (Туреччина): курорт, відпочинок", "Загальний запит про курорт; у ТОП хаби регіону."),
    "urlaub türkei lara": ("відпочинок у Лара (Туреччина)", ""),
    "lara urlaub": ("відпочинок у Лара", ""),
    "urlaub antalya lara": ("відпочинок в Анталії (Лара)", ""),
    "lara urlaub angebote": ("пропозиції відпочинку в Лара", ""),
    "urlaub türkei lara günstig": ("недорогий відпочинок у Лара (Туреччина)", ""),
    "antalya lara urlaub all inclusive mit flug": (f"відпочинок в Анталії (Лара) {AI}, з перельотом", ""),
    "urlaub türkei lara 2026": ("відпочинок у Лара (Туреччина) 2026", ""),
    "last minute urlaub antalya lara": ("гарячі тури в Анталію (Лара)", ""),
    "urlaub lara beach türkei": ("відпочинок на пляжі Лара (Туреччина)", ""),
    "last minute urlaub türkei lara": ("гарячі тури в Лара (Туреччина)", ""),
    "urlaub türkei antalya lara": ("відпочинок у Туреччині: Анталія, Лара", ""),
    "urlaub türkei all inclusive lara": (f"відпочинок у Лара {AI}", ""),
    "lara beach urlaub": ("відпочинок на пляжі Лара", ""),
    "lara all inclusive urlaub": (f"відпочинок у Лара {AI}", ""),
    "billig urlaub in antalya lara": ("дешевий відпочинок в Анталії (Лара)", ""),
    "antalya lara urlaub buchen": ("забронювати відпочинок в Анталії (Лара)", ""),
    "günstig urlaub antalya lara": ("недорогий відпочинок в Анталії (Лара)", ""),
    "günstiger urlaub antalya lara": ("дешевший відпочинок в Анталії (Лара)", "Порівняльний ступінь: шукають вигідніші варіанти."),
    "urlaub lara strand": ("відпочинок на пляжі в Лара", ""),
    "lara urlaub buchen": ("забронювати відпочинок у Лара", ""),
    "urlaub buchen türkei antalya lara": ("забронювати відпочинок у Туреччині (Анталія, Лара)", ""),
    "all inclusive urlaub antalya-lara": (f"відпочинок в Анталії (Лара) {AI}", ""),
    "günstig urlaub in lara": ("недорогий відпочинок у Лара", ""),
    "türkei urlaub günstig all inclusive lara": (f"недорогий відпочинок у Лара {AI}", ""),
    "last minute urlaub lara": ("гарячі тури в Лара", ""),
    "türkei lara urlaub buchen": ("забронювати відпочинок у Лара (Туреччина)", ""),
    "lara türkei strand": ("пляж Лара (Туреччина)", "Інформаційний намір: який там пляж."),
    "türkei lara beach": ("пляж Лара (Туреччина)", ""),
    "türkei urlaub lara strand": ("відпочинок у Лара: пляж", ""),
    "türkei lara sehenswürdigkeiten": ("визначні місця Лара (Туреччина)", "Для опису курорту на сторінці."),
    "wo liegt lara in der türkei": ("де розташована Лара в Туреччині", "Питання для FAQ."),
    "türkei lara urlaub gefährlich": ("чи безпечно відпочивати в Лара (Туреччина)", "Розмовне «gefährlich» — питання про безпеку; для FAQ."),
    "urlaub türkei lara belek": ("відпочинок у Туреччині: Лара та Белек", ""),
    "urlaub türkei lara kundu": ("відпочинок у Туреччині: Лара та Кунду", "Кунду — сусідній курортний район Анталії."),
}
H = {  # hotel lists / selections
    "lara hotels": ("готелі в Лара", ""),
    "türkei hotel lara": ("готелі в Лара (Туреччина)", ""),
    "5 sterne hotels türkei lara": ("5-зіркові готелі в Лара (Туреччина)", ""),
    "10 besten hotels in lara türkei": ("10 найкращих готелів у Лара (Туреччина)", ""),
    "türkei urlaub hotel lara": ("відпочинок у Лара: готелі", ""),
    "urlaub türkei 5 sterne lara": ("відпочинок у 5-зіркових готелях Лара", ""),
    "urlaub türkei all inclusive 5 sterne lara": (f"відпочинок у 5-зіркових готелях Лара {AI}", ""),
}
W = {  # weather and map
    "türkei lara wetter": ("погода в Лара (Туреччина)", ""),
    "wetter lara türkei 30 tage": ("погода в Лара (Туреччина) на 30 днів", ""),
    "wetter lara türkei 16 tage": ("погода в Лара (Туреччина) на 16 днів", ""),
    "türkei lara karte": ("карта Лара (Туреччина)", ""),
    "wetter lara türkei 7 tage": ("погода в Лара (Туреччина) на 7 днів", ""),
    "wetter lara türkei 10-tage": ("погода в Лара (Туреччина) на 10 днів", ""),
    "wetter lara türkei oktober": ("погода в Лара (Туреччина) у жовтні", ""),
    "wetter lara türkei aktuell": ("поточна погода в Лара (Туреччина)", ""),
}
N = {  # single hotels
    "liberty lara türkei": ("готель Liberty Lara у Лара (Туреччина)", ""),
    "fame residence lara & spa türkei": ("готель Fame Residence Lara & Spa у Лара (Туреччина)", ""),
    "grand park lara türkei": ("готель Grand Park Lara у Лара (Туреччина)", ""),
    "türkei lara miracle resort": ("готель Miracle Resort у Лара (Туреччина)", ""),
    "titanic beach lara resort antalya türkei": ("готель Titanic Beach Lara Resort (Лара, Анталія, Туреччина)", ""),
    "hotel royal wings türkei lara": ("готель Royal Wings у Лара (Туреччина)", ""),
    "hotel melas lara türkei": ("готель Melas Lara у Лара (Туреччина)", ""),
    "delphin palace türkei lara": ("готель Delphin Palace у Лара (Туреччина)", ""),
    "türkei hotel baia lara": ("готель Baia Lara (Туреччина)", ""),
    "türkei urlaub lara delphin imperial": ("відпочинок у готелі Delphin Imperial Lara (Туреччина)", ""),
    "türkei urlaub lara delphin diva": ("відпочинок у готелі Delphin Diva (Лара, Туреччина)", ""),
    "türkei urlaub limak lara de luxe": ("відпочинок у готелі Limak Lara De Luxe (Туреччина)", ""),
}
FILTERED = {
    "urlaub lara antalya check24": "бренд конкурента (Check24)",
    "ab in den urlaub türkei lara": "бренд конкурента (ab in den urlaub)",
    "ab in den urlaub lara": "бренд конкурента (ab in den urlaub)",
    "ab in den urlaub antalya-lara": "бренд конкурента (ab in den urlaub)",
    "sherwood exclusive lara ab in den-urlaub": "бренд конкурента (ab in den urlaub) + назва готелю",
    "ramada resort lara ab in den urlaub": "бренд конкурента (ab in den urlaub) + назва готелю",
    "ab in den urlaub limak lara": "бренд конкурента (ab in den urlaub) + назва готелю",
    "adalya elite lara ab in den urlaub": "бренд конкурента (ab in den urlaub) + назва готелю",
    "urlaub türkei lara 2023": "застарілий рік (2023)",
    "urlaub türkei lara 2022": "застарілий рік (2022)",
    "lara türkei wikipedia": "навігаційний запит (Wikipedia)",
    "pauschalreisen türkei lara": "дублікат (множина) «pauschalreise türkei lara», який уже в основному списку",
    "pauschalreise türkei lara": "уже в основному списку (78 ключів)",
}


def main():
    d = json.load(open(os.path.join(ROOT, "lara-demand.json"), encoding="utf-8"))
    kp = os.path.join(ROOT, "keywords.json")
    kw = json.load(open(kp, encoding="utf-8"))
    have = {k["keyword"] for k in kw["keywords"]}
    groups = [("general", G), ("hotels_list", H), ("hotel_name", N)]          # weather/map keywords (W) are not targets -> filtered
    WEATHER_REASON = "інформаційний інтент, у ТОП погодні/картографічні сервіси"
    known = {k for _, m in groups for k in m} | set(FILTERED) | set(W)
    # weather/map keywords added earlier -> remove from the keyword list and move to "filtered"
    kw["keywords"] = [k for k in kw["keywords"] if k.get("lara_group") != "weather_map"]
    have = {k["keyword"] for k in kw["keywords"]}
    for k in W:
        if not any(f["keyword"] == k for f in kw["filtered"]):
            kw["filtered"].append({"keyword": k, "reason": WEATHER_REASON})
    unknown = [r["keyword"] for r in d["keywords"] if r["keyword"] not in known]
    if unknown:
        raise SystemExit(f"unclassified Lara keywords: {unknown}")
    added = 0
    for r in d["keywords"]:
        k = r["keyword"]
        if k in FILTERED:
            if not any(f["keyword"] == k for f in kw["filtered"]) and k not in have:
                kw["filtered"].append({"keyword": k, "reason": "Lara: " + FILTERED[k]})
            continue
        for gname, m in groups:
            if k in m and k not in have:
                kw["keywords"].append({"keyword": k, "volume": r["volume"], "cpc": r["cpc"], "intent": r["intent"], "source": "lara", "kd": r.get("kd"),
                                       "lara_group": gname, "translation_uk": m[k][0], "translation_note_uk": m[k][1]})
                added += 1
    json.dump(kw, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("added", added, "Lara keywords; filtered total", len(kw["filtered"]))


if __name__ == "__main__":
    main()
