#!/usr/bin/env python3
"""Stage 2 deliverables: meta-turkei.xlsx and tz-copywriter-turkei.docx.

python scripts/build_stage2.py
Input: competitors-turkei.json (analyze_competitors.py), embeddings-turkei.json (embed_terms.py).
"""
import json, os, re, statistics
from urllib.parse import urlparse

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(os.path.join(ROOT, "competitors-turkei.json"), encoding="utf-8"))
E = json.load(open(os.path.join(ROOT, "embeddings-turkei.json"), encoding="utf-8"))
comps = [c for c in C["competitors"] if c.get("ok")]
own, N = C["own"], len([c for c in C["competitors"] if c.get("ok")])
host = lambda u: urlparse(u).netloc.replace("www.", "")
nosp = lambda s: len(re.sub(r"\s+", "", s or ""))
GAP_TAG = "підтема-прогалина"

# ---------- semantics: recommended place (similarity tier + volume + stage-1 restrictions) ----------
# keyword -> (place, occurrences, block, why)
PLACE = {
 "türkei urlaub": ("title / H1", "8 (максимум, разом на всій сторінці)", "заголовки (2): H1, H2 «Türkei Urlaub günstig buchen: So sparen Sie»; FAQ (1): питання 2; текст (5): короткий вступ під H1, перший H2 під лістингом, блок «günstig buchen», H3 «Türkei im September», блок про переліт і готель. Title рахується окремо", "головний ключ; розподіл входжень — у розділі 5 ТЗ"),
 "urlaub türkei buchen": ("title", "2", "title (через «Türkei Urlaub … buchen»), перший H2 під лістингом (форма «Urlaub in der Türkei buchen»)", "ядро ≥0.80, найчастотніший суміжний"),
 "türkei urlaub 2026": ("title / H1", "1 + 1 розбавлене", "title і H1 («Türkei Urlaub 2026/2027» — це те саме точне входження, що й головного ключа); у H2 про переліт — форма «Urlaub in der Türkei 2026/2027»", "близькість 0.76 (H2/текст), але 5 400 запитів і рік у title мають 3 з 11 конкурентів → рік беремо в title"),
 "türkei urlaub 2027": ("title / H1", "1", "title і H1 («2026/2027»), окремо не повторювати", "закривається тим самим «2026/2027»"),
 "türkei urlaub günstiger": ("title / H2", "2", "title (слово «günstig»), H2 «Türkei Urlaub günstig buchen: So sparen Sie» і одне речення в тексті цього блоку («Türkei Urlaub günstiger buchen»); обидва входять у ліміт 8", "близькість 0.73 (H2/текст); у ТОП 8 із 9 — хаби країни, «günstig» у title мають 8 з 11 конкурентів → беремо в title і description"),
 "türkei reise": ("текст / H2", "2–3", "перший H2 під лістингом, блок про переліт і готель", "ядро ≥0.80"),
 "türkei urlaub mit flug": ("текст / H2", "1", "description («mit Flug & Hotel»); текст блоку «Urlaub in der Türkei 2026/2027 mit Flug und Hotel» — одне точне входження «Türkei Urlaub mit Flug» (входить у ліміт 8)", "ядро ≥0.80"),
 "kurzurlaub türkei": ("H3", "1–2", "H3 «Kurzurlaub Türkei» у блоці видів відпочинку", "близькість 0.88 (ядро) через спільну основу «Urlaub + Türkei», але 320 запитів і вужчий інтент → не title, а окремий H3"),
 "türkei im oktober urlaub": ("текст", "1", "текст H3 «Türkei im Oktober» (форма «Urlaub in der Türkei im Oktober»)", "ядро ≥0.80 за близькістю; за змістом — підрозділ сезону. Ключ у тексті H3, не в заголовку"),
 "september türkei urlaub": ("текст", "1", "текст H3 «Türkei im September» — одне точне входження («Im September ist ein Türkei Urlaub …»), входить у ліміт 8", "H2/текст. Ключ у тексті H3, не в заголовку"),
 "mai urlaub türkei": ("текст", "1", "текст H3 «Türkei im Mai» (форма «Urlaub in der Türkei im Mai»)", "H2/текст. Ключ у тексті H3, не в заголовку"),
 "türkei strandurlaub": ("H3", "1–2", "H3 «Strandurlaub in der Türkei» у блоці видів відпочинку", "H2/текст"),
 "türkei buchen": ("текст", "1–2", "перший H2 під лістингом, CTA-речення наприкінці блоків", "H2/текст"),
 "reise türkei buchen": ("текст", "1", "блок про переліт і готель («Reise in die Türkei buchen»)", "H2/текст"),
 "türkei urlaub buchen günstig": ("H2", "1", "H2 «Türkei Urlaub günstig buchen: So sparen Sie» (те саме входження, що й у ключа «…günstiger»)", "H2/текст; точний порядок слів у заголовку"),
 "türkei reise günstig": ("текст", "1", "блок «günstig buchen»", "H2/текст"),
 "schnäppchen türkei urlaub": ("текст", "1", "блок «günstig buchen», розбавлена форма «Schnäppchen für den Urlaub in der Türkei»", "H2/текст; точну форму не вписувати, щоб не перевищити ліміт 8"),
 "billig türkei urlaub": ("текст", "1", "блок «günstig buchen», розбавлена форма «billig in die Türkei reisen»; далі — «günstig»", "H2/текст; «billig» звучить дешево, не повторювати"),
 "türkei reise billig": ("FAQ", "1", "відповідь на питання 2 FAQ «Wann ist Türkei Urlaub am günstigsten?»", "H2/текст за близькістю; через слово «billig» — лише у відповіді FAQ"),
 "günstig türkei": ("FAQ", "1", "питання 2 FAQ «Wann ist Türkei Urlaub am günstigsten?»", "<0.65 → FAQ/довгий хвіст"),
 "türkei urlaub 2026 all inclusive mit flug und hotel": ("текст", "1", "блок про переліт і готель: розбавлена форма «Urlaub in der Türkei 2026 – All Inclusive mit Flug und Hotel» з анкором на /all-inclusive", "обмеження етапу 1: «All Inclusive» не основне слово хаба → 1 входження з посиланням"),
 "türkei urlaub all inclusive günstig": ("текст", "1", "блок «günstig buchen»: розбавлена форма з анкором на /all-inclusive", "обмеження етапу 1 → 1 входження з посиланням"),
 "türkei urlaub günstig all inclusive mit flug": ("текст", "0–1", "закривається попередніми двома входженнями (розбавлена форма)", "обмеження етапу 1; точну форму не вписувати"),
 "urlaub türkei 2026 all inclusive": ("FAQ", "1", "питання 3 FAQ «Was kostet ein Urlaub in der Türkei 2026?» з анкором на /all-inclusive у відповіді", "<0.65 → FAQ; обмеження етапу 1"),
 "türkei urlaub 2026 all inclusive mit flug und hotel side": ("текст", "1", "H3 Side у блоці регіонів: розбавлена форма «Urlaub in Side 2026 mit Flug und Hotel» з анкором на /side", "ключ із регіоном: розбавлена форма + посилання на /tour/turkei/side"),
}

SYM_RE = re.compile(r"[^\w\s.,:;!?&–\-/|()€%]")
_c = [c for c in C["competitors"] if c.get("ok")]
SYM = {"check": sum(1 for c in _c if re.search("[✓✔]", c["description"])), "plane": sum(1 for c in _c if "✈" in c["description"]),
       "sun": sum(1 for c in _c if re.search("[☀☼]", c["description"])), "leader": SYM_RE.findall(_c[0]["description"])}
assert not SYM["leader"], SYM
SYM_NOTE = ("Символи: у description не більше двох різних простих символів (✈ ✓ ☀), кожен не більше двох разів, без кольорових емодзі; у title символів немає. "
            f"У конкурентів у description: галочка у {SYM['check']} з {len(_c)}, літачок у {SYM['plane']}, сонце у {SYM['sun']}; у лідера schauinsland символів немає.")
# one consistent set to implement + sets to test later; every set is a matching title-H1 pair
SETS = [
 {"name": "Комплект A", "status": "впроваджувати",
  "cond": "Впроваджувати зараз (title — після запуску /tour/turkei/last-minute).",
  "title": ("Türkei Urlaub 2026/2027 günstig buchen | reisemu.de", "Головний ключ на початку, рік (ключі «türkei urlaub 2026/2027», 5 990 запитів) і «günstig buchen» (ключі «…günstiger», «urlaub türkei buchen»). Та сама формула в ТОП-3: sonnenklar («Türkei Urlaub 2026 / 2027 günstig buchen») і holidaycheck («Türkei Urlaub 2026/2027 • Günstig buchen bei …»). Title holidaycheck узято з даних SERP етапу 1, бо сама сторінка не відкрилася (HTTP 400). Символів немає."),
  "desc": ("Türkei Urlaub 2026/2027 günstig buchen ✈ Reisen mit Flug & Hotel ✓ Antalya, Side, Alanya & Bodrum ✓ Beste Reisezeit & Tipps. Jetzt Angebote vergleichen!", "Початок збігається з title і H1; далі пакет «Flug & Hotel», чотири регіони й сезон — те, що є в блоках сторінки. Символи: ✈ один раз біля «Flug», ✓ двічі. " + SYM_NOTE),
  "h1": ("Türkei Urlaub 2026/2027 günstig buchen", "Дослівно основа title: головний ключ, рік і «günstig buchen».")},
 {"name": "Комплект B", "status": "для тесту після 8–12 тижнів",
  "cond": "Пробувати, якщо через 8–12 тижнів CTR сторінки в GSC нижчий за середній по сайту на тих самих позиціях, або якщо сторінка збирає покази переважно за запитами з «buchen», «mit Flug», «Reise», а не з «günstig».",
  "title": ("Türkei Urlaub buchen: Reisen mit Flug & Hotel 2026/2027", "Без «günstig»: акцент на бронюванні й пакеті «переліт + готель» (ключі «urlaub türkei buchen», «türkei urlaub mit flug», «türkei reise»). Слово Pauschalreise не використано — воно для /pauschalreise."),
  "desc": ("Urlaub in der Türkei buchen: günstige Angebote mit Flug und Hotel an der Türkischen Riviera & Ägäis. Regionen, Reisezeit und Preise im Überblick.", "Без символів: природна форма «Urlaub in der Türkei buchen», семантичні слова «Türkische Riviera», «Ägäis», «Reisezeit»."),
  "h1": ("Türkei Urlaub: Reisen mit Flug & Hotel buchen", "Пара до title комплекту B. Без року — не потребує щорічного оновлення.")},
 {"name": "Комплект C", "status": "для тесту після 8–12 тижнів",
  "cond": "Пробувати, якщо сторінка вийшла в ТОП-10 за «türkei urlaub» або «türkei urlaub günstiger» і треба посилити клікабельність, а лістинг стабільно показує ціни «ab … €». H1 лишається з комплекту A — міняються лише title і description.",
  "title": ("Türkei Urlaub günstig buchen – Angebote 2026 | reisemu.de", "Ціновий акцент («günstig», «Angebote») для кластера K07; рік лише поточний."),
  "desc": ("Türkei Urlaub günstig buchen ✓ Aktuelle Angebote 2026 mit Flug & Hotel ✓ Antalya, Side, Alanya & Bodrum im Preisvergleich. Jetzt Reise sichern!", "Ціновий акцент, як у title; ✓ двічі, інших символів немає."),
  "h1": ("Türkei Urlaub 2026/2027 günstig buchen", "Той самий H1, що в комплекті A: узгоджений із title («Türkei Urlaub günstig buchen»).")},
]
for st in SETS:
    t, d = st["title"][0], st["desc"][0]
    assert len(t) <= 60 and len(d) <= 155, (st["name"], len(t), len(d))
    syms = SYM_RE.findall(d)
    assert set(syms) <= set("✈✓☀") and len(set(syms)) <= 2 and all(syms.count(x) <= 2 for x in set(syms)), (st["name"], syms)
    assert not SYM_RE.findall(t), t

# ---------- semantic terms ----------
TERM_UK = {  # term (lower) -> (translation, where)
 "türkei": ("Туреччина", "H2 / текст"), "türkei urlaub": ("відпочинок у Туреччині", "H2 / текст — у межах ліміту 8 точних входжень на сторінку (розділ 5)"),
 "türkische riviera": ("Турецька Рив'єра", "H2 / текст"), "türkischen riviera": ("Турецька Рив'єра", "H2 / текст"),
 "türkische ägäis": ("Турецьке Егейське узбережжя", "H3 / текст"), "türkischen ägäis": ("Турецьке Егейське узбережжя", "H3 / текст"),
 "türkei reisen": ("подорожі до Туреччини", "текст"), "pauschalurlaub": ("пакетний відпочинок", "лише анкор на /pauschalreise"),
 "antalya": ("Анталія", "H3 / текст"), "side": ("Сіде", "H3 / текст"), "alanya": ("Аланія", "H3 / текст"), "kemer": ("Кемер", "H3 / текст"),
 "bodrum": ("Бодрум", "H3 / текст"), "belek": ("Белек", "H3 / текст"), "marmaris": ("Мармарис", "текст"), "kusadasi": ("Кушадаси", "текст"),
 "fethiye": ("Фетхіє", "текст"), "istanbul": ("Стамбул", "текст"), "kappadokien": ("Каппадокія", "текст"), "pamukkale": ("Памуккале", "текст"),
 "lara": ("Лара (район Анталії)", "H3 / текст (анкор на /antalya/lara)"), "ölüdeniz": ("Олюденіз", "текст"), "ephesos": ("Ефес", "текст"),
 "taurusgebirge": ("гори Тавр", "текст"), "bosporus": ("Босфор", "текст"), "dalyan": ("Дальян", "текст"), "manavgat": ("Манавгат", "текст"),
 "hagia sophia": ("Свята Софія", "текст"), "aspendos": ("Аспендос", "текст"), "lykischen küste": ("Лікійське узбережжя", "текст"),
 "lara beach": ("пляж Лара", "текст"), "blaue lagune": ("Блакитна лагуна (Олюденіз)", "текст"), "mittelmeer": ("Середземне море", "текст"),
 "ägäis": ("Егейське море / узбережжя", "H3 / текст"), "südküste": ("південне узбережжя", "текст"), "mittelmeerküste": ("середземноморське узбережжя", "текст"),
 "ägäisküste": ("егейське узбережжя", "текст"),
 "beste reisezeit": ("найкращий час для подорожі", "H2"), "reiseziele": ("напрямки подорожей", "H2"), "urlaubsorte": ("курорти", "H2"),
 "urlaubsregionen": ("курортні регіони", "H2"), "badeurlaub": ("пляжний (купальний) відпочинок", "H3 / текст"), "strandurlaub": ("пляжний відпочинок", "H3"),
 "familienurlaub": ("сімейний відпочинок", "H3"), "urlaubsangebote": ("пропозиції відпочинку", "H2"), "reiseangebote": ("туристичні пропозиції", "текст"),
 "hotels": ("готелі", "текст"), "strand": ("пляж", "текст"), "strände": ("пляжі", "текст"), "sandstrände": ("піщані пляжі", "текст"),
 "buchten": ("бухти", "текст"), "meer": ("море", "текст"), "küste": ("узбережжя", "текст"), "sonne": ("сонце", "текст"),
 "kultur": ("культура", "текст"), "geschichte": ("історія", "текст"), "sehenswürdigkeiten": ("визначні пам'ятки", "H2"),
 "antiken stätten": ("античні пам'ятки", "текст"), "ausflugsziele": ("місця для екскурсій", "H2 / текст"),
 "temperaturen": ("температури", "текст (таблиця сезонів)"), "klima": ("клімат", "текст"), "wetter": ("погода", "текст / FAQ"),
 "sommer": ("літо", "текст"), "herbst": ("осінь", "текст"), "frühling": ("весна", "текст"), "winter": ("зима", "текст"),
 "oktober": ("жовтень", "H3"), "september": ("вересень", "H3"), "april": ("квітень", "текст"), "mai und oktober": ("травень і жовтень", "текст"),
 "familien": ("сім'ї", "текст"), "kindern": ("діти (з дітьми)", "текст"), "nachtleben": ("нічне життя", "текст"), "restaurants": ("ресторани", "текст"),
 "türkische küche": ("турецька кухня", "текст"), "gastfreundschaft": ("гостинність", "текст"), "türkische lira": ("турецька ліра", "FAQ"),
 "reisepass": ("закордонний паспорт", "FAQ"), "visum": ("віза", "FAQ"), "flugzeit": ("тривалість перельоту", "FAQ"), "anreise": ("як дістатися", "текст"),
 "flug": ("переліт", "H2 / текст"), "preisen": ("ціни", "текст"), "preise": ("ціни", "текст"), "wellness": ("велнес", "текст"),
 "resort": ("курортний готель", "текст"), "aquaparks": ("аквапарки", "текст"), "golfplätze": ("гольф-поля", "текст"),
 "thermalquellen": ("термальні джерела", "текст"), "bootstouren": ("морські прогулянки", "текст"), "basar": ("базар", "текст"),
 "altstadt": ("старе місто", "текст"), "moscheen": ("мечеті", "текст"), "städtetrip": ("міська поїздка", "текст"),
 "orient und okzident": ("Схід і Захід", "текст"), "europa und asien": ("Європа й Азія", "текст"), "direkt am meer": ("просто біля моря", "текст"),
 "erholung": ("відпочинок, відновлення", "текст"), "sightseeing": ("огляд пам'яток", "текст"), "landschaften": ("краєвиди", "текст"),
 "natur": ("природа", "текст"), "last minute": ("гарячі тури", "лише анкор на /last-minute"),
 "all inclusive": ("все включено", "лише анкор на /all-inclusive"), "pauschalreise": ("пакетний тур", "лише анкор на /pauschalreise"),
}


def term_rows():
    rows = {}
    CANON = {"türkischen riviera": "türkische riviera", "türkischen ägäis": "türkische ägäis", "lykischen küste": "lykische küste", "preisen": "preise"}
    NAME = {"türkische riviera": "Türkische Riviera", "türkische ägäis": "Türkische Ägäis", "lykische küste": "Lykische Küste", "preise": "Preise",
            "antiken stätten": "antike Stätten", "kindern": "mit Kindern"}
    def add(t, passed):
        key = t["term"].lower()
        if key not in TERM_UK:
            return
        canon = CANON.get(key, key)
        uk, where = TERM_UK[key]
        if canon in rows:  # same term in another grammatical form: one row, larger number of competitors
            r = rows[canon]
            r["df"], r["sim"], r["passed"] = max(r["df"], t["df"]), max(r["sim"], t["sim_best"]), r["passed"] or passed
            return
        rows[canon] = {"term": NAME.get(canon, t["term"]), "uk": uk, "df": t["df"], "sim": t["sim_best"], "where": where, "passed": passed}
    for t in E["terms"]:
        add(t, True)
    for t in E["terms_below_threshold"]:
        add(t, False)
    return sorted(rows.values(), key=lambda r: (not r["passed"], -r["df"], -r["sim"]))


# ---------- subtopics ----------
ALL_HEADS = [h for r in E["subtopics"] + E["subtopic_singleton_list"] for h in r["headings"]]
THEMES = [  # key, name, regex, on own page (bool), own note
 ("reisezeit", "Найкращий час, клімат, погода (Beste Reisezeit / Klima / Wetter)", r"reisezeit|klima|wetter", False, "є лише блок посилань «Türkei Reisen nach Monaten», тексту про сезон немає"),
 ("regionen", "Регіони та курорти (Reiseziele, Urlaubsorte, Riviera, Ägäis, міста)", r"reiseziel|urlaubsort|urlaubsziel|riviera|ägäis|region|antalya|side\b|alanya|belek|kemer|bodrum|istanbul|kappadokien|marmaris|kusadasi|dalyan|inland|schwarzmeer|beliebte orte", True, "є блок посилань «Beliebte Reiseziele / Reiseziele der Türkei» з цінами, без тексту → розширити"),
 ("guenstig", "Вигідне бронювання, ціни (günstig buchen, Bestpreis)", r"günstig|bestpreis|preis|schnäppchen|sparen", False, "є один абзац про Last-Minute і Frühbucher, окремого розділу немає"),
 ("angebote", "Актуальні пропозиції (Aktuelle Urlaubsangebote)", r"angebot", True, "лістинг «Last-Minute-Angebote»"),
 ("faq", "FAQ (Häufige Fragen, Wissenswertes)", r"\bfaq\b|häufige fragen|wissenswertes", False, "FAQ немає"),
 ("hotels", "Добірки готелів (beliebte Hotels, Unterkünfte)", r"hotel|unterkünfte|resort", True, "блок «Unsere Favoriten in der Türkei»"),
 ("urlaubsarten", "Види відпочинку (Familien-, Bade-, Strandurlaub, для кого)", r"familien|badeurlaub|strand|wellness|adults|luxus|langzeit|reiseformen|urlaubsarten|zu zweit|für wen", False, "є лише посилання (VIP, Familienurlaub, сезони), тексту немає"),
 ("sehenswuerdigkeiten", "Пам'ятки, екскурсії, кухня (Sehenswürdigkeiten, Ausflüge)", r"sehenswürd|ausflug|gesehen haben|kultur|einkaufen|küche|lagune", False, "розділу немає"),
 ("einreise", "В'їзд, безпека, валюта (Einreise, Sicherheit, Währung)", r"einreise|sicher|währung|beachten", False, "розділу немає"),
 ("flug", "Переліт і аеропорти (Flug, Flughäfen)", r"(?<![a-zäöü])flug|fliegen", False, "є лише посилання на сторінки аеропортів вильоту"),
 ("gruende", "Чому Туреччина (Gründe, Vielfalt)", r"gründe|warum|vielfalt|facetten|kontraste", False, "розділу немає"),
]
# embedding says "present" (>=0.75 to an own H2/H3) but the page has no such section: corrected by reading the page
OWN_FIX = {"Sehenswürdigkeiten in der Türkei": (False, "ембедінг 0.86 — через заголовок «Reiseziele der Türkei»; розділу про пам'ятки фактично немає"),
           "Urlaubs-Check: Vielfältige Reiseformen in der Türkei": (False, "ембедінг 0.78 — через загальні слова; розділу про види відпочинку немає"),
           "Beliebte Reiseziele für Ihren Urlaub in der Türkei": (True, "є блок посилань із цінами, без тексту")}


def theme_rows():
    out = {}
    for key, name, rx, on_own, note in THEMES:
        hs = [h for h in ALL_HEADS if re.search(rx, h.split(": ", 1)[1], re.I)]
        hosts = sorted({h.split(": ", 1)[0] for h in hs})
        out[key] = {"name": name, "headings": hs, "n": len(hosts), "hosts": hosts, "on_own": on_own, "note": note, "gap": len(hosts) >= 5 and not on_own}
    return out


THEME = theme_rows()
STRICT = []
for r in E["subtopics"]:
    on, note = r["on_own_page"], f"найближчий заголовок reisemu.de: «{r['own_best_heading']}» ({r['own_best_sim']:.2f})"
    if r["subtopic"] in OWN_FIX:
        on, note = OWN_FIX[r["subtopic"]]
    STRICT.append({**r, "on": on, "note": note, "gap": r["competitors"] >= 5 and not on})

# ---------- numbers ----------
texts = sorted(c["text_chars_nospace"] for c in comps)
MED = int(statistics.median(texts))
rich = [t for t in texts if t >= 8000]
own_seo = own["main_text"].split("## Türkei Reisen nach Monaten")[-1]
OWN_SEO = nosp(own_seo)
RANGE = "7 000–8 500"
cnt = lambda f: sum(1 for c in comps if f(c))
STAT = {
 "faq": cnt(lambda c: c["faq"]["present"]), "faq_schema": cnt(lambda c: c["faq"]["schema_faqpage"]),
 "regions": cnt(lambda c: c["regions"]["block"]), "seasons": cnt(lambda c: c["seasons"]["block"]),
 "tables": cnt(lambda c: c["tables"]["count"] > 0), "lists": cnt(lambda c: c["lists"]["content"] > 0),
 "video": cnt(lambda c: c["videos"] > 0), "prices": cnt(lambda c: c["prices"]["mentions"] > 0),
 "guenstig_title": cnt(lambda c: "günstig" in c["title"].lower()), "year_title": cnt(lambda c: "2026" in c["title"]),
 "guenstig_desc": cnt(lambda c: "günstig" in c["description"].lower()), "month_table": cnt(lambda c: c["seasons"]["month_table"]),
 "main_title": cnt(lambda c: "türkei urlaub" in c["title"].lower()), "main_h1": cnt(lambda c: "türkei urlaub" in " ".join(c["h1"]).lower()),
 "img_med": int(statistics.median(c["images"]["content"] for c in comps)),
}

# ---------- structure of the page ----------
# (level, heading DE, chars, theme key or None, instructions UA)
STRUCT = [
 ("H1", "Türkei Urlaub 2026/2027 günstig buchen", "—", None, "Один H1. Без слів Last-Minute, Pauschalreise, All Inclusive. Точне входження «Türkei Urlaub»."),
 ("вступ", "(без заголовка, одразу під H1)", "150–250", None, "1–2 речення, до 250 символів. Головний ключ «Türkei Urlaub» у першому реченні (точне входження). Більше нічого: далі одразу лістинг."),
 ("лістинг", "(наявний блок пропозицій, без нового заголовка від копірайтера)", "—", None, "Тексту немає. Наявний заголовок лістингу «Last-Minute-Angebote» перейменувати на нейтральний «Aktuelle Angebote» (без «Last-Minute» і без «Türkei Urlaub»). Під лістингом — посилання «Last-Minute-Angebote Türkei» на /tour/turkei/last-minute. Увесь текст нижче починається з H2."),
 ("H2", "Urlaub in der Türkei: Regionen, Reisezeit und Preise im Überblick", "400–500", None, "Перший блок під лістингом, 2 абзаци: чому Туреччина і що читач знайде нижче (регіони, сезон, ціни). Ключі: «Urlaub in der Türkei buchen», «Türkei Reise», «Türkei buchen»; одне точне входження «Türkei Urlaub»."),
 ("H2", "5 gute Gründe für einen Urlaub in der Türkei", "400–500", "gruende", "Нумерований список із п'яти причин, по одному реченню з фактом (кількість сонячних днів, довжина узбережжя, час перельоту, рівень готелів, пам'ятки). Без загальних фраз."),
 ("H2", "Türkei Urlaub günstig buchen: So sparen Sie", "800–900", "guenstig", "Єдиний H2 з точною формою головного ключа. Коли й як бронювати дешевше: Frühbucher проти коротких термінів, міжсезоння, аеропорт вильоту, тривалість. Маркований список із 4–5 порад. У тексті одне точне входження («Türkei Urlaub günstiger buchen»), решта ключів «günstig» — розбавлено. Анкори на /last-minute, /pauschalreise, /all-inclusive."),
 ("H2", "Die beliebtesten Urlaubsregionen in der Türkei", "1 500–1 700", "regionen", "Вступ 2 речення + порівняльна таблиця регіонів + п'ять H3 по 280–320 символів. У кожному H3: для кого, пляж, 1–2 пам'ятки, трансфер з аеропорту."),
 ("H3", "Antalya & Lara", "280–320", "regionen", "Посилання на /tour/turkei/antalya і /tour/turkei/antalya/lara."),
 ("H3", "Side", "280–320", "regionen", "Посилання на /tour/turkei/side; одне речення з формою «Urlaub in Side 2026 mit Flug und Hotel»."),
 ("H3", "Alanya", "280–320", "regionen", "Посилання на наявну /tour/turkei/alanya."),
 ("H3", "Belek & Kemer", "280–320", "regionen", "Посилання на наявну /tour/turkei/kemer."),
 ("H3", "Bodrum & Türkische Ägäis", "280–320", "regionen", "Посилання на наявну /tour/turkei/bodrum; згадати Marmaris, Fethiye, Kusadasi."),
 ("H2", "Beste Reisezeit für die Türkei", "1 000–1 200", "reisezeit", "Вступ 2–3 речення + таблиця за місяцями + три H3 по 200–250 символів. Наприкінці — посилання «Beste Reisezeit Türkei» на /tour/turkei/reisezeit (листопад і грудень докладно там)."),
 ("H3", "Türkei im Mai", "200–250", "reisezeit", "Ключ «mai urlaub türkei» — у тексті, форма «Urlaub in der Türkei im Mai»."),
 ("H3", "Türkei im September", "200–250", "reisezeit", "Ключ «september türkei urlaub» — у тексті, одне точне входження «Türkei Urlaub» («Im September ist ein Türkei Urlaub …»)."),
 ("H3", "Türkei im Oktober", "200–250", "reisezeit", "Ключ «türkei im oktober urlaub» — у тексті, форма «Urlaub in der Türkei im Oktober»; температура води, осінні канікули."),
 ("H2", "Urlaubsarten: Strandurlaub, Familienurlaub & Kurzurlaub", "850–950", "urlaubsarten", "Три H3 по 250–300 символів. Тут одне речення з анкором «All Inclusive Urlaub Türkei» на /all-inclusive."),
 ("H3", "Strandurlaub in der Türkei", "250–300", "urlaubsarten", "Ключ «türkei strandurlaub»; Sandstrände, Buchten, Lara Beach, Kleopatra-Strand."),
 ("H3", "Familienurlaub in der Türkei", "250–300", "urlaubsarten", "Aquaparks, пологий вхід у море, які регіони для сімей."),
 ("H3", "Kurzurlaub Türkei", "250–300", "urlaubsarten", "Ключ «kurzurlaub türkei»: 3–5 ночей, Antalya або Istanbul, тривалість перельоту."),
 ("H2", "Urlaub in der Türkei 2026/2027 mit Flug und Hotel", "450–550", "flug", "Аеропорти прильоту (Antalya AYT, Dalaman, Bodrum, Izmir), тривалість перельоту з Німеччини, що входить у пакет. Одне точне входження «Türkei Urlaub mit Flug»; ще «Türkei Reise», «Reise in die Türkei buchen». Одне речення з анкором «Pauschalreise Türkei» на /pauschalreise і одне — з анкором на /all-inclusive."),
 ("H2", "Sehenswürdigkeiten & Ausflüge in der Türkei", "450–550", "sehenswuerdigkeiten", "Маркований список із 5–6 місць (Pamukkale, Kappadokien, Ephesos, Istanbul, Aspendos, Ölüdeniz) по одному реченню."),
 ("H2", "Häufige Fragen zum Urlaub in der Türkei", "1 100–1 300", "faq", "6 питань, відповідь 180–220 символів кожна. Розмітка FAQPage. У відповідях точну форму «Türkei Urlaub» не вживати."),
]
FAQ = [
 ("Wann ist die beste Reisezeit für die Türkei?", "neckermann, restplatzboerse, lidl, sonnenklar; посилання на /tour/turkei/reisezeit"),
 ("Wann ist Türkei Urlaub am günstigsten?", "holidayplatz («Wann Türkei Urlaub buchen für günstige Preise?»); ключі «günstig türkei», «türkei reise billig». Єдине питання з точною формою «Türkei Urlaub»"),
 ("Was kostet ein Urlaub in der Türkei 2026?", "holidayplatz («Was kostet Türkei All Inclusive mit Flug?»); ключ «urlaub türkei 2026 all inclusive» з анкором на /all-inclusive у відповіді"),
 ("Welche Region in der Türkei eignet sich am besten für Familien?", "restplatzboerse, holidayplatz, sonnenklar"),
 ("Welche Dokumente brauche ich für die Türkei und ist das Land aktuell sicher?", "lidl, sonnenklar, holidayplatz; коротка відповідь і посилання «Reisehinweise Türkei» на /tour/turkei/reisehinweise — подробиці лише там"),
 ("Welche Währung hat die Türkei und wie bezahlt man am besten?", "neckermann, sonnenklar"),
]
EXACT = re.compile(r"türkei urlaub", re.I)
EX_HEAD = [h for l, h, *_ in STRUCT if l in ("H1", "H2", "H3") and EXACT.search(h)]
EX_FAQ = [q for q, _ in FAQ if EXACT.search(q)]
EX_TEXT = ["короткий вступ під H1 (перше речення)", "перший H2 під лістингом «Urlaub in der Türkei: Regionen, Reisezeit und Preise im Überblick»",
           "блок «Türkei Urlaub günstig buchen» («Türkei Urlaub günstiger buchen»)", "H3 «Türkei im September» («Im September ist ein Türkei Urlaub …»)",
           "блок про переліт і готель («Türkei Urlaub mit Flug»)"]
EX_LIMIT = 8
assert len(EX_HEAD) == 2 and len(EX_FAQ) == 1 and len(EX_HEAD) + len(EX_FAQ) + len(EX_TEXT) <= EX_LIMIT, (EX_HEAD, EX_FAQ)
_rng = lambda c: [int(x.replace(" ", "")) for x in c.split("–")]
SUM_LO = sum(_rng(c)[0] for l, h, c, k, i in STRUCT if l in ("H2", "вступ"))
SUM_HI = sum(_rng(c)[-1] for l, h, c, k, i in STRUCT if l in ("H2", "вступ"))
LINKS = [
 ("/tour/turkei/last-minute", "нова", "Last-Minute-Angebote Türkei; Last Minute Türkei", "під лістингом, блок «günstig buchen»"),
 ("/tour/turkei/pauschalreise", "нова", "Pauschalreise Türkei; Pauschalreisen in die Türkei", "блок «günstig buchen», блок про переліт і готель"),
 ("/tour/turkei/all-inclusive", "існує", "All Inclusive Urlaub Türkei; Türkei All Inclusive", "блок видів відпочинку, блок «günstig buchen», FAQ про ціну"),
 ("/tour/turkei/antalya", "існує", "Urlaub in Antalya; Antalya Urlaub", "H3 «Antalya & Lara», таблиця регіонів"),
 ("/tour/turkei/antalya/lara", "нова", "Lara Urlaub; Hotels in Lara", "H3 «Antalya & Lara»"),
 ("/tour/turkei/side", "існує", "Urlaub in Side; Side Urlaub", "H3 «Side», таблиця регіонів"),
 ("/tour/turkei/reisehinweise", "нова", "Reisehinweise Türkei; Einreise & Sicherheit in der Türkei", "FAQ, питання 5 (окремого блоку про в'їзд і безпеку на хабі немає)"),
 ("/tour/turkei/reisezeit", "нова", "Beste Reisezeit Türkei; Türkei im November und Dezember", "кінець блоку «Beste Reisezeit», перше питання FAQ"),
 ("/tour/turkei/alanya, /kemer, /bodrum", "існують", "Urlaub in Alanya; Kemer Urlaub; Bodrum Urlaub", "відповідні H3 блоку регіонів (додатково до обов'язкових)"),
]

# =====================================================================================================
# XLSX
# =====================================================================================================
HEAD_FILL, GAP_FILL, OK_FILL, GREY = PatternFill("solid", fgColor="1F3864"), PatternFill("solid", fgColor="FCE4D6"), PatternFill("solid", fgColor="E2EFDA"), PatternFill("solid", fgColor="EDEDED")


def sheet(wb, name, header, rows, widths, note=None):
    ws = wb.create_sheet(name)
    r0 = 1
    if note:
        ws.cell(1, 1, note).alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(header))
        ws.row_dimensions[1].height = 15 * (1 + len(note) // 150)
        r0 = 2
    for j, h in enumerate(header, 1):
        c = ws.cell(r0, j, h)
        c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), HEAD_FILL, Alignment(wrap_text=True, vertical="center")
    for i, row in enumerate(rows, r0 + 1):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, v).alignment = Alignment(wrap_text=True, vertical="top")
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    ws.auto_filter.ref = f"A{r0}:{get_column_letter(len(header))}{r0 + len(rows)}"
    return ws, r0


def build_xlsx():
    wb = Workbook()
    wb.remove(wb.active)
    # Семантика
    kw = sorted(E["keywords"], key=lambda r: -r["volume"])
    rows = [[k["keyword"], k["translation"], k["volume"], k["sim_main"], PLACE[k["keyword"]][0], k["tier"], f"{k['closest_adjacent']} ({k['sim_closest_adjacent']:.2f})",
             PLACE[k["keyword"]][1], PLACE[k["keyword"]][2], PLACE[k["keyword"]][3]] for k in kw]
    sheet(wb, "Семантика", ["ключ", "переклад", "частотність", "близькість до головного", "рекомендоване місце (title / H1 / H2 / текст / FAQ)", "рівень за близькістю",
                           "найближчий суміжний ключ (близькість)", "к-ть входжень", "блок сторінки", "пояснення"], rows, [44, 44, 12, 12, 24, 18, 40, 10, 52, 62],
          note=f"Близькість — косинусна, модель {E['model']} (відкрита модель, не Google): орієнтир поруч із частотністю й аналізом ТОП, а не замість них. Пороги: ≥0.80 — ядро, 0.65–0.80 — H2/текст, <0.65 — FAQ/довгий хвіст. Де рекомендоване місце відрізняється від рівня за близькістю, причина — у колонці «пояснення».")
    # Мета-теги
    rows = []
    for st in SETS:
        for el, key, lim in (("Title", "title", "до 60"), ("Description", "desc", "до 155"), ("H1", "h1", "—")):
            rows.append([st["name"], st["status"], el, st[key][0], len(st[key][0]), lim, st[key][1], st["cond"]])
    rows += [["Зараз на сайті", "для порівняння", "Title", own["title"], own["title_len"], "до 60", "Довший за 60 символів і містить головні ключі трьох інших сторінок (Last-Minute, Pauschalreisen, All-inclusive), а головного ключа «Türkei Urlaub» у ньому немає.", ""],
             ["Зараз на сайті", "для порівняння", "Description", own["description"], own["description_len"], "до 155", "Теж про all inclusive і Last-Minute Pauschalreisen; містить кольоровий емодзі.", ""],
             ["Зараз на сайті", "для порівняння", "H1", " | ".join(own["h1"]), len(" | ".join(own["h1"])), "—", "Лише головний ключ, без року й «günstig buchen».", ""]]
    ws, r0 = sheet(wb, "Мета-теги", ["комплект", "статус", "елемент", "текст (німецькою)", "довжина", "ліміт", "пояснення", "коли застосовувати / умова тесту"], rows, [16, 22, 13, 78, 10, 9, 90, 70],
                   note="Перший комплект (A) — узгоджені title + description + H1, його впроваджувати. Комплекти B і C — для тесту після 8–12 тижнів, кожен зі своєю умовою. Title хаба міняти після запуску /tour/turkei/last-minute (етап 1: зараз сторінка має позицію 23 за «türkei last minute»). «günstig» узято в title і description, бо «türkei urlaub günstiger» (3 600) ранжується саме на хабах країни (8 із 9), а слово є в title у %d з %d конкурентів. %s" % (STAT["guenstig_title"], N, SYM_NOTE))
    for i, row in enumerate(rows, r0 + 1):
        fill = OK_FILL if row[1] == "впроваджувати" else (GREY if row[0].startswith("Зараз") else None)
        if fill:
            for j in range(1, 9):
                ws.cell(i, j).fill = fill
    # Конкуренти
    def pos(c):
        p = c.get("serp_positions") or {}
        return "; ".join(f"{k}: {v}" for k, v in sorted(p.items(), key=lambda x: (x[0] != C["main_keyword"], x[1]))) or "—"
    def comp_row(c, label=None):
        return [c["url"], label or pos(c), c["title"], c["description"], " | ".join(c["h1"]), c["text_chars_nospace"],
                f"{c['lists']['content']} (+{c['lists']['link_lists']} списків посилань)", c["tables"]["count"],
                f"{c['images']['content']} (alt: {c['images']['with_alt']})",
                ("так, %d питань%s" % (len(c["faq"]["questions"]), ", FAQPage" if c["faq"]["schema_faqpage"] else "")) if c["faq"]["present"] else "ні",
                ("так: " + ", ".join((c["regions"]["in_headings"] or c["regions"]["in_link_anchors"])[:8])) if c["regions"]["block"] else "ні",
                ("так: " + "; ".join(c["seasons"]["headings"][:2])) if c["seasons"]["block"] else "ні",
                c["h2_count"], c["h3_count"], c["videos"], c["prices"]["mentions"], c["reviews"]["mentions"],
                "так" if c["filters"]["search_form"] else "ні", c["cta"]["count"], ", ".join(c["keywords_exact_any"]) or "—",
                "; ".join(x for x in [c.get("note"), ("замінює " + c["replaces"]) if c.get("replaces") else None] if x) or ""]
    rows = [comp_row(c) for c in comps]
    rows.append(comp_row(own, "власна сторінка (поза ТОП-10)"))
    rows[-1][5] = f"{own['text_chars_nospace']} (з них SEO-тексту ≈{OWN_SEO}, решта — службові повідомлення пошуку)"
    rows[-1][-1] = "сторінка reisemu.de для порівняння; відкрита з браузерним User-Agent (на UA плагіна сайт відповідає 403)"
    for r in C["summary"]["replaced"]:
        rows.append([r["failed"], "не відкрилася", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
                     f"HTTP {r['status']}: {r['error']}. Заміна: {r['replacement']} — {'відкрилася' if r['replacement_ok'] else 'теж не відкрилася (HTTP 403)'}"])
    rows.append([f"МЕДІАНА ({N} конкурентів)", "", "", "", "", MED, int(statistics.median(c["lists"]["content"] for c in comps)),
                 int(statistics.median(c["tables"]["count"] for c in comps)), STAT["img_med"], f"FAQ у {STAT['faq']} з {N}", f"у {STAT['regions']} з {N}", f"у {STAT['seasons']} з {N}",
                 statistics.median(c["h2_count"] for c in comps), statistics.median(c["h3_count"] for c in comps), f"у {STAT['video']} з {N}", "", "", "", "", "", ""])
    ws, r0 = sheet(wb, "Конкуренти", ["URL", "позиція (ключ: місце)", "title", "description", "H1", "обсяг тексту (симв. без пробілів)", "списки", "таблиці", "фото", "FAQ",
                                     "блок регіонів", "блок сезонів", "H2", "H3", "відео", "згадок цін", "згадок відгуків", "форма пошуку", "CTA", "ключі хаба (точне входження)", "примітка"],
                   rows, [52, 30, 44, 60, 36, 16, 16, 9, 14, 20, 40, 40, 6, 6, 7, 9, 10, 9, 7, 40, 60])
    for i, row in enumerate(rows, r0 + 1):
        fill = OK_FILL if row[1].startswith("власна") else (GAP_FILL if row[1] == "не відкрилася" else (GREY if str(row[0]).startswith("МЕДІАНА") else None))
        if fill:
            for j in range(1, 22):
                ws.cell(i, j).fill = fill
    # Семантичні слова
    tr = term_rows()
    rows = [[t["term"], t["uk"], f"{t['df']} з {N}", t["sim"], t["where"], "так (≥0.60)" if t["passed"] else "ні (<0.60): відібрано за частотою в конкурентів"] for t in tr]
    ws, r0 = sheet(wb, "Семантичні слова", ["термін", "переклад укр.", "у скількох конкурентів", "близькість (макс. до головного/суміжних)", "де використати (H2 / текст / FAQ)", "пройшов поріг близькості"],
                   rows, [30, 38, 14, 16, 40, 44],
                   note=f"Умову «близькість ≥0.60 і ≥3 конкурентів» пройшли лише {sum(t['passed'] for t in tr)} термінів із {E['terms_candidates_df3']} кандидатів (зелені рядки): модель дає високу близькість тільки фразам зі словами «Türkei»/«Urlaub», а окремим іменникам і назвам курортів («Side» 0.09, «Strand» 0.19) — низьку. Тому нижче додано терміни, що є у ≥3 конкурентів, але не пройшли поріг: їх відібрано вручну за змістом (без загальних слів на кшталт Welt, Auswahl, Kombination). Близькість — орієнтир відкритої моделі, а не Google.")
    for i, t in enumerate(tr, r0 + 1):
        if t["passed"]:
            for j in range(1, 7):
                ws.cell(i, j).fill = OK_FILL
    # Підтеми
    rows = []
    for key, *_ in THEMES:
        t = THEME[key]
        rows.append([t["name"], " | ".join(t["headings"][:8]), f"{t['n']} з {N}", "так" if t["on_own"] else "ні", "так" if t["gap"] else "ні", "укрупнена тема (об'єднання заголовків за змістом)", t["note"]])
    for r in STRICT:
        rows.append([r["subtopic"], " | ".join(r["headings"][:8]), f"{r['competitors']} з {N}", "так" if r["on"] else "ні", "так" if r["gap"] else "ні", "кластер ембедінгів (близькість ≥0.75)", r["note"]])
    rows.sort(key=lambda r: (r[5].startswith("укрупнена"), -int(r[2].split()[0])))
    ws, r0 = sheet(wb, "Підтеми", ["підтема", "приклади заголовків конкурентів", "у скількох конкурентів", "є на reisemu.de (так/ні)", "прогалина (так/ні)", "метод", "примітка"],
                   rows, [52, 110, 12, 12, 12, 34, 70],
                   note=f"Спочатку — кластери H2/H3 за близькістю ≥0.75 (як у завданні): {E['headings_total']} заголовків {N} конкурентів, показано кластери з ≥2 конкурентами. Прогалина = у ≥5 конкурентів і немає на reisemu.de. Поріг 0.75 дробить одну тему на кілька кластерів (наприклад, «Türkische Riviera», «Türkische Ägäis», «Beliebte Reiseziele»), тому нижче додано укрупнені теми: ті самі заголовки, згруповані за змістом, з кількістю унікальних конкурентів. Наявність на reisemu.de звірено зі сторінкою вручну; де це розходиться з ембедінгом, причина — у примітці.")
    for i, row in enumerate(rows, r0 + 1):
        if row[4] == "так":
            for j in range(1, 8):
                ws.cell(i, j).fill = GAP_FILL
    wb.save(os.path.join(ROOT, "meta-turkei.xlsx"))
    return tr


# =====================================================================================================
# DOCX
# =====================================================================================================
def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def table(doc, header, rows, widths=None, gap_col=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for j, h in enumerate(header):
        c = t.rows[0].cells[j]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, "1F3864")
    for row in rows:
        cells = t.add_row().cells
        for j, v in enumerate(row):
            cells[j].text = ""
            run = cells[j].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9)
            if gap_col is not None and GAP_TAG in str(row[gap_col]):
                shade(cells[j], "FCE4D6")
    if widths:
        for row in t.rows:
            for j, w in enumerate(widths):
                row.cells[j].width = Cm(w)
    doc.add_paragraph()
    return t


def build_docx(tr):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(1.8)
        s.top_margin = s.bottom_margin = Cm(1.6)
    P = lambda text, bold=False: (lambda p: (setattr(p.runs[0], "bold", bold), p)[1])(doc.add_paragraph(text))
    B = lambda text: doc.add_paragraph(text, style="List Bullet")

    doc.add_heading("ТЗ для копірайтера: хаб «Türkei Urlaub»", 0)
    P("Сторінка: https://reisemu.de/tour/turkei · мова тексту: німецька (de-DE), звертання на «Sie» · інструкції українською, заголовки й ключі німецькою.")
    P(f"Основа: {N} сторінок-хабів із ТОП-10 google.de за ключами «türkei urlaub», «urlaub türkei buchen», «türkei urlaub 2026 all inclusive mit flug und hotel», «türkei urlaub günstiger» (SERP від 7 жовтня 2026), 25 ключів хаба (93 880 запитів на місяць).")

    doc.add_heading("1. Мета сторінки, аудиторія, інтент", 1)
    B("Мета: головна сторінка напрямку «Туреччина». Вона має ранжуватися за «türkei urlaub» (60 500 запитів) і суміжними запитами та вести відвідувача до лістингу пропозицій і до підсторінок (регіони, Last Minute, Pauschalreise, All Inclusive, довідкові гайди).")
    B("Аудиторія: мешканці Німеччини, які планують пляжний відпочинок у Туреччині з перельотом — сім'ї з дітьми, пари, ті, хто шукає вигідну ціну. Регіон і дати часто ще не обрано.")
    B("Інтент: комерційний з елементом вибору. Людина хоче побачити ціни й пропозиції, а також зрозуміти, який регіон і місяць обрати. Текст не замінює лістинг, а допомагає обрати й переводить на пропозиції.")
    B("Тон: конкретний і корисний — цифри (температура, час перельоту, трансфер), без рекламних штампів на кшталт «Traumurlaub wartet».")

    doc.add_heading("2. Обсяг тексту", 1)
    P(f"Рекомендований обсяг: {RANGE} символів без пробілів (приблизно 1 100–1 300 слів).", True)
    B(f"Сума блоків зі структури в розділі 3 — {SUM_LO:,}–{SUM_HI:,} символів.".replace(",", " "))
    B(f"Медіана {N} конкурентів — {MED:,} символів без пробілів; розкид від {texts[0]:,} до {texts[-1]:,}.".replace(",", " "))
    B(f"П'ять хабів із розгорнутим текстом мають {rich[0]:,}–{rich[-1]:,} символів (holidayplatz, lidl-reisen, restplatzboerse, sonnenklar, schauinsland); три сторінки майже без тексту (travelantis, aldi-reisen, check24) тягнуть медіану вниз.".replace(",", " "))
    B(f"Тому діапазон узято в 1,6–1,9 раза вище медіани, на нижній межі текстових лідерів. Блоку про в'їзд і безпеку на хабі немає (це тема /tour/turkei/reisehinweise). Зараз на reisemu.de близько {OWN_SEO:,} символів SEO-тексту (чотири абзаци внизу сторінки).".replace(",", " "))

    doc.add_heading("3. Структура H1–H3", 1)
    P(f"Позначка «{GAP_TAG}» стоїть біля блоків, які є щонайменше у 5 з {N} конкурентів і яких немає на reisemu.de. Обсяг H2 включає його H3. Порядок на сторінці: H1 → 1–2 речення → лістинг → увесь текст, починаючи з H2.")
    rows = []
    for lvl, head, chars, key, instr in STRUCT:
        mark = ""
        if key and lvl == "H2":
            t = THEME[key]
            mark = f"{GAP_TAG} ({t['n']} з {N})" if t["gap"] else f"{t['n']} з {N}" + ("; на сайті лише посилання" if key in ("regionen",) else "")
        rows.append([lvl, head, chars, mark, instr])
    table(doc, ["рівень", "заголовок (німецькою)", "обсяг, симв. без пробілів", "у конкурентів", "що писати"], rows, [1.4, 5.0, 2.2, 3.0, 6.2], gap_col=3)
    strict_gaps = [r for r in STRICT if r["gap"]]
    P("Прогалини за кластерами ембедінгів (заголовки з близькістю ≥0.75, у ≥5 конкурентів): " + "; ".join(f"«{r['subtopic']}» ({r['competitors']} з {N})" for r in strict_gaps) + ". Решта позначок — за укрупненими темами (аркуш «Підтеми» у meta-turkei.xlsx).")

    doc.add_heading("4. Списки, таблиці, фото, FAQ", 1)
    doc.add_heading("Списки", 2)
    B("Блок «günstig buchen»: маркований список із 4–5 порад, як заощадити (по одному реченню).")
    B("Блок «Sehenswürdigkeiten & Ausflüge»: маркований список із 5–6 місць, назва жирним + одне речення.")
    B("Блок «5 gute Gründe»: нумерований список із п'яти пунктів.")
    B(f"Змістовні списки є у {STAT['lists']} з {N} конкурентів; більше трьох списків на сторінку не потрібно.")
    doc.add_heading("Таблиці", 2)
    B("Таблиця 1, блок регіонів — порівняння курортів. Колонки: Region | Strand | Ideal für | Transfer ab Flughafen | Preis ab. Рядки: Antalya/Lara, Side, Alanya, Belek, Kemer, Bodrum. Ціни «ab … €» замовник підставляє з лістингу. Схожу таблицю має лише holidayplatz.")
    B("Таблиця 2, блок «Beste Reisezeit» — місяці. Колонки: Monat | Lufttemperatur | Wassertemperatur | Geeignet für. Рядки: April–Oktober (7 рядків) і один рядок «November–März». Кліматичні дані брати з climate-data.org: середні багаторічні значення для Antalya (температура повітря вдень і температура води). Якщо температури води для Antalya там немає — брати її з seatemperature.info для Antalya. Значення округлювати до цілих градусів. Над таблицею одне речення, що дані наведено для Турецької Рив'єри (Antalya); для Ägäis (Bodrum) вода в середньому на 1–2 °C холодніша.")
    B(f"Таблицю за місяцями не має жоден із {N} конкурентів (таблиці взагалі є у {STAT['tables']}), тож це спосіб виділитися.")
    doc.add_heading("Фото", 2)
    B("Усього 9–10 фото: 1 головне (узбережжя Рив'єри), 5 — по одному на кожен H3 регіонів, 1 — до блоку сезону, 2 — види відпочинку (пляж, сім'я), 1 — пам'ятки (Pamukkale або Kappadokien).")
    B("До кожного фото копірайтер дає унікальний alt німецькою з назвою місця, наприклад «Konyaaltı-Strand in Antalya mit Blick auf das Taurusgebirge». Зараз на сторінці шість зображень з однаковим alt «Türkei Urlaub».")
    B(f"Медіана у конкурентів — {STAT['img_med']} зображень, але більшість із них — картки готелів у лістингу.")
    doc.add_heading("FAQ", 2)
    P(f"FAQ є у {STAT['faq']} з {N} конкурентів, розмітку FAQPage мають {STAT['faq_schema']}. Шість питань, відповідь 180–220 символів:")
    table(doc, ["№", "питання (німецькою)", "звідки питання / що врахувати"], [[i, q, s] for i, (q, s) in enumerate(FAQ, 1)], [0.8, 8.5, 8.5])

    doc.add_heading("5. Обов'язкові ключі", 1)
    P("Кількість — точні входження або природна форма з тими самими словами («Urlaub in der Türkei buchen» зараховується за «urlaub türkei buchen»). Порядок — за частотністю.")
    kw = sorted(E["keywords"], key=lambda r: -r["volume"])
    table(doc, ["ключ", "частотність", "близькість", "місце", "входжень", "блок"],
          [[k["keyword"], k["volume"], f"{k['sim_main']:.2f}", PLACE[k["keyword"]][0], PLACE[k["keyword"]][1], PLACE[k["keyword"]][2]] for k in kw], [4.6, 1.6, 1.5, 2.6, 1.5, 6.0])
    P(f"Точна форма «Türkei Urlaub»: не більше {EX_LIMIT} входжень на всій сторінці (заголовки + текст + FAQ; title і description не рахуються). У конкурентів у тексті вона трапляється 0–6 разів, медіана 2. Розподіл:", True)
    table(doc, ["де", "кількість", "місця"],
          [["заголовки", len(EX_HEAD), "; ".join("«%s»" % h for h in EX_HEAD)], ["FAQ", len(EX_FAQ), "; ".join("«%s»" % q for q in EX_FAQ) + " (у відповідях — 0)"],
           ["текст", len(EX_TEXT), "; ".join(EX_TEXT)], ["разом", len(EX_HEAD) + len(EX_FAQ) + len(EX_TEXT), f"ліміт {EX_LIMIT}"]], [2.5, 1.8, 13.5])
    P("Усі інші ключі, що містять слова «türkei urlaub» (schnäppchen, billig, варіанти з All Inclusive, травень і жовтень), вписувати розбавлено — через «Urlaub in der Türkei».")

    doc.add_heading("6. Семантичне ядро тексту", 1)
    P(f"Слова й словосполучення з текстів конкурентів. Колонка «у конкурентів» показує, на скількох із {N} сторінок термін трапляється. Кожен термін достатньо вжити 1–2 рази у вказаному місці; назви регіонів з H3 — 2–3 рази.")
    P(f"Примітка: близькість рахує відкрита модель {E['model']}, а не Google. Це орієнтир поруч із частотністю й аналізом ТОП, а не заміна їм. Поріг ≥0.60 пройшли лише {sum(t['passed'] for t in tr)} термінів (позначені «так»): модель високо оцінює тільки фрази зі словами «Türkei» чи «Urlaub». Решту відібрано за частотою в конкурентів і змістом.")
    table(doc, ["термін", "переклад", "у конкурентів", "близькість", "де використати", "поріг ≥0.60"],
          [[t["term"], t["uk"], f"{t['df']} з {N}", f"{t['sim']:.2f}", t["where"], "так" if t["passed"] else "ні"] for t in tr], [3.6, 4.2, 1.9, 1.7, 4.6, 1.8])

    doc.add_heading("7. Внутрішні посилання", 1)
    P("Кожна сторінка отримує 1–2 посилання з тексту; анкори чергувати, не повторювати той самий анкор двічі. Посилання на сторінки зі станом «нова» ставити після їх запуску.")
    table(doc, ["сторінка", "стан", "анкори (німецькою)", "де в тексті"], [list(l) for l in LINKS], [5.0, 1.6, 6.0, 5.2])
    have = {l["href"].rstrip("/") for l in own.get("internal_links", [])}
    now = [p for p, *_ in LINKS[:8] if "https://reisemu.de" + p in have]
    P("Зараз хаб посилається лише на " + ", ".join(now) + " з восьми обов'язкових сторінок.")

    doc.add_heading("8. Заборони", 1)
    B("Не використовувати «Last-Minute», «Pauschalreise» («Pauschalurlaub») і «All Inclusive» у title, H1, H2, H3 і вступі. Ці слова — лише в анкорах посилань на відповідні сторінки й у реченні навколо анкора, не більше 2 згадок кожного на весь текст.")
    B("Не оптимізувати текст під головні ключі інших сторінок: «pauschalreise türkei», «last minute türkei», «all-inclusive urlaub türkei», «urlaub side türkei», «lara türkei», «hotel türkei», «reise türkei warnung», «türkei rundreise».")
    B(f"Без переспаму: «Türkei Urlaub» у точній формі — не більше {EX_LIMIT} разів на всій сторінці: {len(EX_HEAD)} у заголовках (H1 і один H2), {len(EX_FAQ)} у питанні FAQ, {len(EX_TEXT)} у тексті (розподіл — у розділі 5). В інших заголовках, у відповідях FAQ і в alt фото точної форми немає; чергувати з «Urlaub in der Türkei», «Türkei Reise», «Ferien in der Türkei».")
    B("Не змінювати формулювання заголовків зі структури так, щоб у них з'явилася точна форма «Türkei Urlaub».")
    B("Слово «billig» — не більше двох разів на текст; далі «günstig», «preiswert», «zum kleinen Preis».")
    B("Не вписувати довгі ключі дослівно, якщо фраза звучить неприродно («türkei urlaub günstig all inclusive mit flug»): достатньо, щоб слова стояли в одному реченні.")
    B("Не писати про погоду по днях, курс валют і чинні попередження МЗС із конкретними датами — це зміст /reisezeit і /reisehinweise; на хабі лише короткий підсумок і посилання.")
    B("Не вигадувати ціни, рейтинги й відгуки. Ціни «ab … €» підставляє замовник із лістингу.")
    B("Без тексту, згенерованого шаблонно під кожен регіон: у кожному H3 мають бути факти саме про цей курорт.")

    doc.add_heading("9. Що конкуренти роблять краще і як їх обійти", 1)
    P("Що вони роблять краще:", True)
    B(f"Текст. Медіана {MED:,} символів проти приблизно {OWN_SEO:,} на reisemu.de; у п'яти лідерів 8 400–12 100.".replace(",", " "))
    B(f"Блок регіонів (заголовки або добірка посилань на курорти) має {STAT['regions']} з {N} конкурентів, у більшості з текстом; на reisemu.de це лише посилання з цінами.")
    B(f"Блок про сезон і клімат — {STAT['seasons']} з {N}; FAQ — {STAT['faq']} з {N}. На reisemu.de немає ні того, ні того.")
    B(f"Title. «Türkei Urlaub» у title мають {STAT['main_title']} з {N}, слово «günstig» — {STAT['guenstig_title']}, рік — {STAT['year_title']}. Title reisemu.de має 88 символів і містить Last-Minute, Pauschalreisen та All-inclusive, а головного ключа в ньому немає.")
    B("Структуровані дані: check24 і holidayplatz мають AggregateRating, три сторінки — FAQPage; на reisemu.de розмітки JSON-LD не знайдено.")
    P("Як обійти:", True)
    B("Таблиця за місяцями з температурою повітря й води — її немає в жодного з конкурентів.")
    B("Порівняльна таблиця регіонів із реальними цінами «ab … €» з власного лістингу (ціни за регіонами на сторінці вже є). Серед конкурентів таку таблицю має лише holidayplatz.")
    B("Окремий блок «günstig buchen» з конкретними порадами: у конкурентів це здебільшого один рекламний абзац, хоча ключ «türkei urlaub günstiger» ранжується саме на хабах.")
    B("FAQ із шістьма питаннями та розміткою FAQPage; відповідь про документи й безпеку веде на власний гайд /tour/turkei/reisehinweise.")
    B("Чітке розведення тем: хаб не конкурує з власними сторінками Last Minute, Pauschalreise і All Inclusive, а посилається на них — у schauinsland, anextour і restplatzboerse ці слова змішані в заголовках хаба.")
    B("Унікальні alt у фото й зміст-навігація (якорі на H2) на початку сторінки, як у schauinsland.")
    P("Чого текст не вирішить: розмітку JSON-LD (FAQPage, BreadcrumbList) додають розробники. Крім того, у HTML сторінки під час перевірки були повідомлення «keine passenden Angebote» — можливо, це прихований шаблон, але лістинг варто перевірити.")

    doc.add_heading("10. Мета-теги", 1)
    a = SETS[0]
    doc.add_heading("Впроваджувати: комплект A", 2)
    P("Один узгоджений комплект: title, description і H1 починаються однаково. Title міняти після запуску /tour/turkei/last-minute.")
    table(doc, ["елемент", "текст (німецькою)", "довжина", "пояснення"],
          [["Title", a["title"][0], f"{len(a['title'][0])} (до 60)", a["title"][1]], ["Description", a["desc"][0], f"{len(a['desc'][0])} (до 155)", a["desc"][1]],
           ["H1", a["h1"][0], len(a["h1"][0]), a["h1"][1]]], [2.2, 6.4, 1.8, 7.4])
    doc.add_heading("Для тесту після 8–12 тижнів", 2)
    P("Не впроваджувати одразу. Кожен комплект пробувати лише за своєї умови й міняти title разом із парним H1; порівнювати CTR і позиції в GSC за 4 тижні до і після.")
    for st in SETS[1:]:
        P(f"{st['name']}. Умова: {st['cond']}", True)
        table(doc, ["елемент", "текст (німецькою)", "довжина", "пояснення"],
              [["Title", st["title"][0], f"{len(st['title'][0])} (до 60)", st["title"][1]], ["Description", st["desc"][0], f"{len(st['desc'][0])} (до 155)", st["desc"][1]],
               ["H1", st["h1"][0], len(st["h1"][0]), st["h1"][1]]], [2.2, 6.4, 1.8, 7.4])
    doc.add_heading("Зараз на сайті (для порівняння)", 2)
    table(doc, ["елемент", "текст", "довжина"], [["Title", own["title"], own["title_len"]], ["Description", own["description"], own["description_len"]], ["H1", " | ".join(own["h1"]), len(" | ".join(own["h1"]))]], [2.2, 13.0, 2.6])
    doc.save(os.path.join(ROOT, "tz-copywriter-turkei.docx"))


if __name__ == "__main__":
    tr = build_xlsx()
    build_docx(tr)
    for st in SETS:
        print(st["name"], st["status"], "| title", len(st["title"][0]), "| desc", len(st["desc"][0]), "| h1", len(st["h1"][0]))
    print("symbols in competitor descriptions", SYM)
    print("exact: headings", len(EX_HEAD), EX_HEAD, "| faq", len(EX_FAQ), EX_FAQ, "| text", len(EX_TEXT))
    print("median", MED, "rich", rich, "own seo", OWN_SEO, "stats", STAT)
    print("terms", len(tr), "passed", sum(t["passed"] for t in tr))
    for k, t in THEME.items():
        print(f"theme {k}: {t['n']}/{N} own={t['on_own']} gap={t['gap']}  {t['hosts']}")
    print("strict gaps", [(r["subtopic"], r["competitors"]) for r in STRICT if r["gap"]])
    lo, hi = SUM_LO, SUM_HI
    print([t for t in tr if t["term"] == "Preise"], "terms", len(tr))
    print("structure sum", lo, hi)
