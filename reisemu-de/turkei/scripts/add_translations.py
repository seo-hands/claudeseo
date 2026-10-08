#!/usr/bin/env python3
"""Store Ukrainian translations (by meaning and search intent, not word for word) in keywords.json.

python scripts/add_translations.py [--force]
Fields added to every keyword: translation_uk, translation_note_uk (only for typos/colloquial forms/ambiguous words).
Existing translations are kept unless --force (so keywords are not translated twice).
Terminology: Reise/Urlaub -> подорож/відпочинок, Pauschalreise -> пакетний тур (переліт + готель), last minute -> гарячі тури,
all inclusive -> «все включено», Rundreise -> екскурсійний тур (з маршрутом), Reisewarnung -> попередження щодо подорожей.
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI = "«все включено»"
T = {
    "türkei urlaub": ("відпочинок у Туреччині", ""),
    "reise türkei warnung": ("попередження щодо подорожей до Туреччини", "Розмовний порядок слів; йдеться про офіційне попередження (Reisewarnung) і чи безпечно зараз їхати."),
    "all-inclusive urlaub türkei": (f"відпочинок у Туреччині за системою {AI}", ""),
    "pauschalreise türkei": ("пакетний тур до Туреччини (переліт + готель)", ""),
    "urlaub side türkei": ("відпочинок у Сіде (Туреччина)", ""),
    "urlaub türkei buchen": ("забронювати відпочинок у Туреччині", ""),
    "türkei urlaub 2026": ("відпочинок у Туреччині 2026", ""),
    "türkei urlaub 2026 all inclusive mit flug und hotel": (f"відпочинок у Туреччині 2026 {AI}, з перельотом і готелем", ""),
    "hotel türkei": ("готелі Туреччини", "Однина замість множини — це запит на добірку готелів."),
    "türkei urlaub günstiger": ("дешевший відпочинок у Туреччині", "Порівняльний ступінь: шукають вигідніші варіанти, ніж зазвичай."),
    "türkei urlaub reisewarnung": ("відпочинок у Туреччині: попередження щодо подорожей", "Інформаційний намір: чи діє застереження і чи безпечно їхати."),
    "türkei reise": ("подорож до Туреччини", ""),
    "last minute türkei": ("гарячі тури до Туреччини", ""),
    "türkei urlaub all inclusive günstig": (f"недорогий відпочинок у Туреччині {AI}", ""),
    "türkei urlaub günstig all inclusive mit flug": (f"недорогий відпочинок у Туреччині {AI}, з перельотом", ""),
    "pauschalreise türkei all inclusive": (f"пакетний тур до Туреччини {AI}", ""),
    "last minute urlaub türkei": ("гарячі тури на відпочинок у Туреччині", ""),
    "türkei im oktober urlaub": ("відпочинок у Туреччині в жовтні", ""),
    "urlaub türkei 2026 all inclusive": (f"відпочинок у Туреччині 2026 {AI}", ""),
    "türkei rundreise": ("екскурсійний тур Туреччиною", "Rundreise — тур із маршрутом по кількох містах/регіонах, а не відпочинок в одному готелі."),
    "pauschalreisen türkei 2026": ("пакетні тури до Туреччини 2026", ""),
    "last minute türkei all inclusive": (f"гарячі тури до Туреччини {AI}", ""),
    "pauschalreise günstig türkei": ("недорогий пакетний тур до Туреччини", "Порядок слів розмовний."),
    "türkei buchen": ("забронювати поїздку до Туреччини", "Скорочена форма: тур, готель або переліт — не уточнено."),
    "türkei urlaub 2026 all inclusive mit flug und hotel side": (f"відпочинок у Сіде 2026 {AI}, з перельотом і готелем", "Назва курорту стоїть в кінці ключа, схоже на допис до довгого запиту."),
    "türkei urlaub 2027": ("відпочинок у Туреччині 2027", ""),
    "last minute urlaub türkei all inclusive": (f"гарячі тури до Туреччини {AI}", ""),
    "pauschalreise side türkei": ("пакетний тур до Сіде (Туреччина)", ""),
    "reise türkei mit personalausweis": ("поїздка до Туреччини з німецьким ID-посвідченням (Personalausweis)", "Personalausweis — внутрішнє посвідчення особи громадянина Німеччини (ID-картка), питання: чи можна їхати без закордонного паспорта."),
    "türkei reise personalausweis": ("поїздка до Туреччини за ID-карткою (Personalausweis)", "Те саме питання про в'їзд без паспорта."),
    "personalausweis für türkei reise": ("ID-картка (Personalausweis) для поїздки до Туреччини", "Те саме питання про в'їзд без паспорта."),
    "reise türkei buchen": ("забронювати поїздку до Туреччини", ""),
    "pauschalreisen türkei all inclusive günstig": (f"недорогі пакетні тури до Туреччини {AI}", ""),
    "türkei strandurlaub": ("пляжний відпочинок у Туреччині", ""),
    "türkei urlaub buchen günstig": ("забронювати недорогий відпочинок у Туреччині", ""),
    "türkei urlaub mit flug": ("відпочинок у Туреччині з перельотом", ""),
    "türkei antalya last minute": ("гарячі тури в Анталію (Туреччина)", ""),
    "türkei reise günstig": ("недорога подорож до Туреччини", ""),
    "günstig in die türkei fliegen": ("дешеві перельоти до Туреччини (авіаквитки)", "Інтент — перельоти, а не тур; тому це слабко комерційний запит для турагентства."),
    "november türkei urlaub": ("відпочинок у Туреччині в листопаді", "Часто шукають погоду та чи є сезон."),
    "september türkei urlaub": ("відпочинок у Туреччині у вересні", ""),
    "super last minute türkei all inclusive": (f"супергарячі тури до Туреччини {AI}", "«Super last minute» — виліт у найближчі дні."),
    "türkei reise aktuell": ("подорож до Туреччини: актуальна ситуація", "Розмовне «aktuell» — актуальна ситуація, новини, безпека."),
    "kurzurlaub türkei": ("короткий відпочинок у Туреччині (на кілька днів)", ""),
    "türkei last minute angebote": ("гарячі пропозиції турів до Туреччини", ""),
    "last minute türkei antalya all inclusive": (f"гарячі тури в Анталію {AI}", ""),
    "mai urlaub türkei": ("відпочинок у Туреччині в травні", ""),
    "all inclusive reise türkei": (f"поїздка до Туреччини {AI}", ""),
    "türkei reise last minute": ("гарячі тури до Туреччини", ""),
    "türkei reise billig": ("дешева поїздка до Туреччини", "Billig — «дешево» з відтінком «якнайдешевше»."),
    "günstig türkei": ("вигідні тури до Туреччини", "Скорочена розмовна форма без іменника: «тур/відпочинок» не вказано, дослівно «дешево Туреччина»."),
    "dezember türkei urlaub": ("відпочинок у Туреччині в грудні", ""),
    "pauschalreisen türkei last minute": ("гарячі пакетні тури до Туреччини", ""),
    "pauschalreise türkei all inclusive 2026": (f"пакетний тур до Туреччини {AI} 2026", ""),
    "pauschalreise türkei side all inclusive": (f"пакетний тур до Сіде {AI}", ""),
    "reise türkei side": ("поїздка до Сіде (Туреччина)", ""),
    "reise türkei sicher": ("чи безпечно їхати до Туреччини", "Розмовне «sicher» — питання про безпеку поїздки."),
    "billig türkei urlaub": ("дешевий відпочинок у Туреччині", ""),
    "türkei urlaub meer": ("відпочинок на морі в Туреччині", ""),
    "türkei urlaub pauschalreise": ("відпочинок у Туреччині за пакетним туром", ""),
    "pauschalreise türkei lara": ("пакетний тур до Лари (курортний район Анталії)", "Лара — район Анталії з готелями біля моря."),
    "ferien türkei": ("канікули або відпустка в Туреччині", "Ferien — шкільні канікули, у розмовній мові також відпустка."),
    "flugreise türkei": ("тур із перельотом до Туреччини", ""),
    "schnäppchen türkei urlaub": ("відпочинок у Туреччині за акційною ціною", "Schnäppchen — «вдала знахідка», дуже вигідна пропозиція з великою знижкою."),
    "rundreise türkei mit badeurlaub": ("екскурсійний тур Туреччиною з пляжним відпочинком", ""),
    "türkei rundreise 7 tage": ("екскурсійний тур Туреччиною на 7 днів", ""),
    "türkei rundreise 14 tage": ("екскурсійний тур Туреччиною на 14 днів", ""),
    "türkei kappadokien rundreise": ("екскурсійний тур Туреччиною з Каппадокією", ""),
    "türkei rundreise 2026": ("екскурсійний тур Туреччиною 2026", ""),
    "türkei rundreise 10 tage": ("екскурсійний тур Туреччиною на 10 днів", ""),
    "türkei rundreise 149 euro": ("екскурсійний тур Туреччиною від 149 євро", "Ціна з конкретної пропозиції."),
    "türkei rundreise kappadokien und baden": ("екскурсійний тур Туреччиною: Каппадокія та пляжний відпочинок", ""),
    "türkei rundreise auf eigene faust": ("самостійна подорож Туреччиною за власним маршрутом", "«Auf eigene Faust» — без турфірми та організованої групи."),
    "türkei rundreise und baden": ("екскурсійний тур Туреччиною з пляжним відпочинком", "«Baden» — купання/пляжний відпочинок."),
    "2 wochen türkei rundreise": ("екскурсійний тур Туреччиною на 2 тижні", ""),
    "türkei rundreise istanbul kappadokien pamukkale": ("екскурсійний тур: Стамбул, Каппадокія, Памуккале", ""),
    "rundreise schwarzmeerküste türkei": ("екскурсійний тур узбережжям Чорного моря (Туреччина)", ""),
    "rundreise türkei mit istanbul": ("екскурсійний тур Туреччиною зі Стамбулом", ""),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    p = os.path.join(ROOT, "keywords.json")
    d = json.load(open(p, encoding="utf-8"))
    main_kw = [k for k in d["keywords"] if k.get("source") != "lara"]      # Lara keywords are translated in add_lara.py
    missing = [k["keyword"] for k in main_kw if k["keyword"] not in T]
    extra = [k for k in T if k not in {x["keyword"] for x in main_kw} | {f["keyword"] for f in d["filtered"]}]    # filtered ones keep their translation entry
    if missing or extra:
        raise SystemExit(f"translation set does not match keywords.json: missing={missing}, extra={extra}")
    n = 0
    for k in main_kw:
        if a.force or not k.get("translation_uk"):
            k["translation_uk"], k["translation_note_uk"] = T[k["keyword"]]
            n += 1
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"translated {n} of {len(main_kw)} keywords")


if __name__ == "__main__":
    main()
