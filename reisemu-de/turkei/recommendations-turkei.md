# Рекомендації для https://reisemu.de/tour/turkei

Перерахунок виконано скілом `semantics-travel` (режим recluster, без запитів до API; рішення — `semantics-decisions.json`, налаштування — секція `## semantics-travel` у CLAUDE.md).

Дані: DataForSEO Labs (частотність, KD, CPC, інтент), читання сторінок сайту (title, контент) і SERP google.de, зібраний 7 жовтня 2026 через live/regular з `location_code` 2276 + `se_domain` google.de (тека `serp-raw-regular/`). Аналіз охоплює 77 ключів (ще «günstig in die türkei fliegen» (390) відфільтровано як запит про авіаквитки, не тур), сумарна частотність 171 370 запитів на місяць. Для «türkei urlaub» видача збігається з ручною перевіркою в браузері (8 із 8 доменів); інші 77 ключів вибірково не перевірялися, і видача може змінюватись між запусками. Ключі Lara (42 + 12 назв готелів; 8 погодних/картографічних відфільтровано) додано за даними `lara-demand.json` (Labs + 7 SERP-запитів), без змін у загальній SERP-вибірці. Переклади ключів українською (за змістом і пошуковим наміром) лежать у `keywords.json` (`translation_uk`) та в `semantics-turkei.xlsx`.

## Як визначено сторінку
Кластери за лемою та інтентом (16) залишаються основою групування. Сторінку для кожного ключа визначає тип посадкових сторінок конкурентів у ТОП:
- кожен URL ТОП-10 класифіковано (хаб країни / хаб регіону / last minute / all inclusive / pauschalreise / готель / інформаційна / rundreise / Frühbucher / інше); правила редагуються в `scripts/analyze.py`;
- типи одного продукту рахуються разом (сторінка країни + сторінки регіонів);
- підбірки пропозицій туроператора («Flug+Hotel», сторінки місць `/ort/`, заголовки з Urlaub/Pauschalreise/last minute) — це хаби країни чи регіону, а не сторінки готелів; готель — лише сторінка конкретного готелю чи список готелів агрегатора (профіль `de.json`, тип `hub_listing`);
- ≥5 із ~9 результатів одного типу → рекомендована сторінка цього типу; 3–4 → «спірно», перевірка за парами сторінок одного домену; ≤2 → окрема сторінка не потрібна, ключ іде на ширшу;
- регіональна сторінка-матриця (наприклад `/tour/turkei/antalya/last-minute`) обирається лише для ключа, у якому названо регіон;
- лемний кластер розщеплюється (K01a, K01b…), якщо його ключі за типом ТОП ведуть на різні сторінки;
- **бізнес-правило (редагується в `BUSINESS_RULES`):** ключі з «Pauschalreise/Pauschalreisen» ведуть на `/tour/turkei/pauschalreise`, бо хаб під цей запит не оптимізуємо, але **лише якщо в ключі немає назви регіону (Side, Antalya, Lara…) і немає іншого головного типу туру** (last minute; all inclusive, написаний до слова Pauschalreise). Такі ключі розподіляються за типом ТОП або матрицею. Ключ позначається «за бізнес-правилом», якщо SERP-частка pauschalreise-сторінок <5. Окреме рішення власника (`KEYWORD_OVERRIDES`): «pauschalreise türkei side all inclusive» → `/side/pauschalreise` разом з «pauschalreise side türkei»;
- сторінки `/reisezeit`, `/ratgeber`, `/side/pauschalreise` лишаються окремими; мінімального порогу обсягу для окремої сторінки немає.

## Стан сторінки
- Тип і інтент: хаб країни, комерційний («Türkei Urlaub»). Title зараз «Türkei Urlaub - Last-Minute-Angebote», H1 «Türkei Urlaub».
- Контент: лістинг із 12 пропозицій на 7 ночей і 3 короткі абзаци тексту. Блоків про регіони, сезон і FAQ немає.
- reisemu.de не потрапив у ТОП-10 google.de за жодним із 77 ключів. За Labs сторінка ранжується лише за двома запитами, на позиції 23: «türkei last minute» (1 000) і «last minute urlaub türkei all inclusive» (590).

## Фінальний розподіл по сторінках

| Сторінка | Стан | Кластери | Частотність |
|---|---|---|---|
| /tour/turkei | існує | K01a, K03b, K07, K09, K10a, K05c | 93 880 |
| /tour/turkei/reisehinweise | нова | K02, K11 | 31 430 |
| /tour/turkei/antalya/lara | нова | L01, L02, K13b | 9 930 |
| /tour/turkei/pauschalreise | нова | K04, K01c | 14 100 |
| /tour/turkei/all-inclusive | існує | K03a | 10 110 |
| /tour/turkei/side | існує | K05a | 6 770 |
| /tour/turkei/last-minute | нова | K06 | 6 140 |
| /hotels/turkei | нова | K08 | 4 400 |
| /tour/turkei/rundreisen | нова | K12, K14, K15, K16 | 1 860 |
| /tour/turkei/side/pauschalreise | нова (матриця) | K05b | 800 |
| /tour/turkei/antalya/last-minute | нова (матриця) | K13a, L03 | 850 |
| /tour/turkei/antalya | існує | — (власних ключів немає; батьківська сторінка для матриць /lara і /last-minute) | 0 |
| /tour/turkei/reisezeit | нова | K10b | 600 |
| /tour/turkei/ratgeber | нова | K01b | 310 |
| /tour/turkei/antalya | існує | — (власних ключів немає; батьківська сторінка матриць) | 0 |

Разом 181 180 запитів: 77 основних ключів (171 370) і 42 ключі Lara (9 810, без назв готелів і погоди). Ще 30 170 запитів — назви готелів Lara (аркуш «Готелі Lara»), на сторінки готелів; 10 250 запитів погоди й карти відфільтровано (аркуш «Відфільтровані»). З 77 основних ключів 62 лишилися на тих самих сторінках, що були за лемою, 15 змінили сторінку.

## Які ключі змінили сторінку (15 із 77)
- **Antalya + last minute → матриця `/tour/turkei/antalya/last-minute` (850):** «türkei antalya last minute» (480): 6 із 9 таких сторінок; ще три ключі Lara + last minute (50) — «last minute urlaub antalya lara», «last minute urlaub türkei lara», «last minute urlaub lara» — за рішенням власника; «last minute türkei antalya all inclusive» (320): 3 із 9, спірно, але підтверджено перевіркою.
- **Чотири довгі AI-ключі (8 600) → хаб** `/tour/turkei`: AI-сторінок у ТОП менше 5. AI-сторінці лишаються «all-inclusive urlaub türkei» (9 900) і «all inclusive reise türkei» (210).
- **November і Dezember (600) → `/tour/turkei/reisezeit`:** у ТОП 8 із 8 і 6 із 7 результатів — інформаційні.
- **«türkei urlaub meer» і «ferien türkei» (310) → `/tour/turkei/ratgeber`.**
- **Відфільтровано: «günstig in die türkei fliegen» (390)** — запит про авіаквитки, не тур (був у K07 на хабі).
- **Side + Pauschalreise → матриця `/tour/turkei/side/pauschalreise` (800):** «pauschalreise side türkei» (590): 8 із 9; «pauschalreise türkei side all inclusive» (210) — за рішенням власника (за ТОП було б `/side`, 4 із 7, спірно).
- **«flugreise türkei» (140) → `/pauschalreise`** (5 із 9).
- **«türkei urlaub 2026 all inclusive mit flug und hotel side» (590) → хаб:** регіональних AI-сторінок Side менше 5.
- **«pauschalreise türkei lara» (170) → нова сторінка `/tour/turkei/antalya/lara`** (рішення власника; за ТОП було б `/antalya`, 6 із 9 — готелі Lara). «pauschalreisen türkei last minute» (210) лишається на `/tour/turkei/last-minute` (5 із 9): у ній є інший тип туру, тож бізнес-правило Pauschalreise не діє.

## Ключі «за бізнес-правилом» (5 ключів, 3 890 запитів)
SERP-частка pauschalreise-сторінок <5, тому ключ іде на `/pauschalreise` не за типом ТОП:

| Ключ | Частотність | Сторінка за ТОП |
|---|---|---|
| pauschalreise türkei all inclusive | 1 600 | хаб (спірно, не перевірено) |
| pauschalreisen türkei 2026 | 880 | `/pauschalreise` (4 із 9, спірно → підтверджено) |
| pauschalreise günstig türkei | 720 | хаб (рекомендовано: хаби країни й регіонів 6 із 9) |
| pauschalreisen türkei all inclusive günstig | 480 | хаб (спірно, не перевірено) |
| pauschalreise türkei all inclusive 2026 | 210 | `/pauschalreise` (3 із 9, спірно → підтверджено) |

Головний «pauschalreise türkei» (9 900) має 7 pauschalreise-сторінок із 9 і «türkei urlaub pauschalreise» (170) — 5; для них бізнес-правило збігається з ТОП.

## Що не підтвердилось
- **K07 (günstig).** «türkei urlaub günstiger» і «türkei urlaub buchen günstig» лишаються на хабі (8 із 9). «türkei reise günstig» (5 хабів проти 4 last-minute/Frühbucher) і «schnäppchen türkei urlaub» (4 хаби проти 3) на `/last-minute` не переходять: за правилом хаб виграє, а в другому випадку жоден тип не дотягує до 5. Кластер K07 цілий лишається на хабі.
- **«urlaub türkei buchen» (6 600) позначено «перевірити вручну».** Його ТОП розкиданий: pauschalreise (країна) 2, хаб країни 2, готелі регіону 2, готель 1, хаб регіону 1, інше 1; спільних URL із «türkei urlaub» немає. Тимчасово лишається на хабі.
- **«türkei urlaub günstig all inclusive mit flug» (1 600)** лишається на хабі: після виправлення класифікації (logitravel «Flug+Hotel» і place-сторінки операторів — хаби) у ТОП хабів 4, готелів 3, тож 3–4 із 9 і «спірно (не перевірено)».
- **10 спірних випадків без перевірки** (3–4 із 9) лишаються на хабі, окремі сторінки під них не створюються.

## Перевірка спірних (render_page.py, безкоштовно, 12 пар)
Результати в `landing-verification.json` і в аркуші «Перевірка спірних».
- **All inclusive проти хабу:** sonnenklar.tv («Türkei Urlaub günstig buchen» і «Türkei All Inclusive Urlaub», 891 і 616 слів власного тексту) та lidl-reisen.de («Urlaub Türkei» і «Türkei All Inclusive Urlaub», 1 073 і 1 045 слів); збіг тексту ≈0 → окрема посадкова, не фільтр.
- **Pauschalreise проти хабу:** sonnenklar.tv (891 і 379 слів) та coraltravel.de (1 474 і 1 875 слів); збіг ≈0 → окрема посадкова.
- **Last minute Antalya проти хабу Antalya:** обидві сторінки разом є лише у lidl-reisen.de («Urlaub Antalya» і «Last Minute Urlaub Antalya», 1 063 і 961 слів, збіг 0). У sonnenklar (667 слів власного тексту), TUI (169) і ANEX (власного тексту немає) є лише Last-Minute-Antalya, хабу Antalya немає (404). Підтверджено частково.
- **Готелі проти хабу:** tui.com/hotels/tuerkei («Türkei Hotel», 780 слів) окрема від tui.com/urlaub/tuerkei; holidaycheck повернув 400, restplatzboerse рендериться JS. Після уточнення класифікації «hotel türkei» (4 400) має 4 готельні сторінки із 7 і стало «рекомендовано», тож вердикт щодо `/hotels/turkei` більше не потрібен; «спірно → підтверджено» лишилось у 2 ключів.
- **Обмеження перевірки:** ціни й набір пропозицій рендеряться динамічно (кількість згадок цін 0), тож «той самий лістинг із фільтром» за пропозиціями не порівнювалось, лише за H1 і текстом.

## Рекомендації

1. **Зробити /tour/turkei хабом «Türkei Urlaub» і змінити title.**
   Хаб країни домінує в ТОП. Кластер K01a (74 960): «türkei urlaub» (60 500, KD 12; 7 із 8 результатів — хаби), «urlaub türkei buchen», 2026/2027, Strand, Kurzurlaub. Разом з іншими кластерами хаба це 93 880 запитів (55% усього простору). Title: напрям «Türkei Urlaub buchen 2026/2027 – günstig mit Flug & Hotel»; слово «Last-Minute» прибрати (див. п. 3); слово Pauschalreise в title і H1 хаба не використовувати (бізнес-правило).

2. **Додати на хаб те, що мають конкурентні хаби з ТОП.**
   - Блок регіонів (Antalya, Side, Kemer, Alanya, Bodrum, Belek) з лінками на підсторінки.
   - Секція «Günstig buchen»: цінові фільтри, ціни від, акції (K07).
   - Місяці Oktober, September, Mai — секція «Beste Reisezeit» на хабі; November і Dezember ведуть на `/reisezeit`.
   - FAQ про документи і безпеку з посиланням на гайд з п. 7.
   - Текст 800–1 200 слів замість трьох абзаців (конкуренти мають 600–1 500 слів власного тексту на хабі).

3. **Розвести last-minute: зараз сторінки конкурують.**
   /tour/turkei оптимізована під «Last-Minute-Angebote» і ранжується за last minute (поз. 23), а ще є загальна /last-minute-reisen. Кластер K06 (6 140): у ТОП «last minute türkei» 8 із 9 результатів — last-minute-сторінки. Створити /tour/turkei/last-minute, а title головної міняти лише після її запуску, щоб не втратити позицію 23. Лінкувати з /last-minute-reisen. Матриця `/tour/turkei/antalya/last-minute` (850) — другий крок, коли основна last-minute-сторінка працює.

4. **Розвести /tour/turkei/all-inclusive і хаб.**
   Сторінка існує, але показує той самий блок «Last-Minute-Angebote», що й /tour/turkei (видно зі змісту обох сторінок), і має майже порожній текст. Їй належить K03a (10 110): «all-inclusive urlaub türkei» (9 900; у ТОП лише 3 із 7 результатів — AI-сторінки, тобто спірно, але тип підтверджений перевіркою) і «all inclusive reise türkei» (210; 5 AI-сторінок). Окрема посадкова підтверджена перевіркою (sonnenklar, lidl). Дати унікальний набір пропозицій (AI, 4–5★) і текст 600–1 000 слів.

5. **Створити /tour/turkei/pauschalreise.**
   Сторінка збирає 14 100 запитів: головний «pauschalreise türkei» (9 900; 7 із 9 результатів — pauschalreise-сторінки), варіанти з «günstig», 2026, All Inclusive (5 ключів за бізнес-правилом, 3 890 запитів) і «türkei urlaub pauschalreise», «flugreise türkei». Ключі з регіоном (Side, Lara) або last minute сюди не потрапляють. Конкуренти мають окремі сторінки (sonnenklar, coraltravel, TUI), перевірка підтвердила їх як окремі посадкові. Перетин із хабом за SERP: у ТОП «pauschalreise günstig türkei» 6 із 9 — хаби (країни й регіонів), тож розведіть H1 і текст.

6. **Підсилити /tour/turkei/side та /tour/turkei/antalya.**
   Side (K05a, 6 770): «urlaub side türkei» (6 600): 7 із 9 результатів — хаби Side. Матриця `/side/pauschalreise` (800: «pauschalreise side türkei» і «pauschalreise türkei side all inclusive») окрема лише після появи основної сторінки. `/tour/turkei/antalya` лишилась без власних ключів: Antalya + last minute (850) пішли в матрицю, Lara — на окрему сторінку (п. 8); вона лишається батьківською для обох. Обидві регіональні сторінки зараз лише лістинг («Urlaub in Side», «Reisen in Side monatlich»). Додати унікальний текст, готелі, сезон. Kemer, Alanya, Belek і Bodrum не перевірялися.

7. **Низький пріоритет: гайди, Rundreisen, готелі.**
   - `/reisehinweise` (31 430): «reise türkei warnung» (27 100) і суміжні: 87% результатів — інформаційні. Достатньо FAQ на хабі, окремий гайд необов'язковий. Гайди `/reisezeit` (600) і `/ratgeber` (310) лишаються окремими сторінками за вашим рішенням, без порогу обсягу.
   - Rundreisen (1 860): 4 кластери, у ТОП переважають Rundreise-сторінки (116 із 132). Окрема сторінка лише якщо компанія продає Rundreise.
   - «hotel türkei» (4 400): 4 із 7 готельних сторінок; хаб `/hotels/turkei` (готельні сторінки сайту вже є).

8. **Окрема сторінка Lara: `/tour/turkei/antalya/lara` (за рішенням власника).**
   Обсяг сторінки **9 930 запитів на місяць**: загальні ключі (L01) 6 630, підбірки готелів (L02) 3 130 і «pauschalreise türkei lara» 170.
   Підтвердження за ТОП: «lara türkei» — 7 із 8 хабів Lara (holidaycheck, alltours, dertour, lidl, neckermann, check24, its), «urlaub türkei lara» — 9 із 9 хабів, «türkei hotel lara» — 7 із 7 готелів, «lara hotels» — 6 із 9 готелів. Правило ≥5 виконується для загальних запитів і підбірок готелів. Власний SERP зібрано лише для 5 із 40 ключів сторінки, для решти тип ТОП «н/д».
   Що має бути на сторінці: опис курорту (де розташована Лара, пляж, визначні місця) для ключів «lara türkei», «türkei lara sehenswürdigkeiten», «wo liegt lara…»; **список готелів Лара з фільтрами 4–5★ і All Inclusive** (L02: «lara hotels», «türkei hotel lara», «5 sterne hotels türkei lara», «10 besten hotels…»); короткий блок «Beste Reisezeit» (без прив'язки до ключів); FAQ («чи безпечно відпочивати в Лара», «де розташована Лара»); посилання на сторінки окремих готелів. Title — напрям «Lara Antalya Urlaub: Hotels & Strand»; слово Pauschalreise в H1 не використовувати.
   **Погода й карта не цільові:** 8 ключів («türkei lara wetter» 5 400, «wetter lara türkei 30 tage» 1 600, «…16 tage» 880, «türkei lara karte» 720 та ін., разом 10 250) відфільтровано з причиною «інформаційний інтент, у ТОП погодні/картографічні сервіси» (для «türkei lara wetter» 8 із 10 результатів — wetter.com, wetteronline, meteoblue).

9. **Готельні сторінки: можливість приблизно 30 170 запитів.**
   12 ключів із назвами готелів Lara мають 30 170 запитів на місяць (Liberty Lara 12 100, Fame Residence Lara & Spa 8 100, Grand Park Lara 3 600, Miracle Resort 2 400, Titanic Beach Lara 2 400, Royal Wings 720, Melas Lara 480 та ін.; аркуш «Готелі Lara»). Рекомендація — сторінки окремих готелів на сайті, не сторінка Lara. Готельні сторінки сайту вже існують (`/hotels/turkei/...`), їхній ТОП інший: для «liberty lara türkei» 8 із 9 результатів — готельні сторінки й відгуки (loveholidays, HolidayCheck), а для «fame residence lara & spa türkei» 7 із 9 — відео й соцмережі (YouTube, Facebook, TikTok, Instagram) і лише один готель. Тож реально лише частина обсягу доступна (брендові запити зазвичай забирають сторінки готелю й агрегатори); SERP збирався лише для двох готелів.

10. **Напрямки розширення (аркуш «Напрямки розширення»).**
   Суміжні теми, які не належать до ядра хабу `/tour/turkei`, але мають попит (11 тем, 72 ключі, 31 180 запитів): Side (8 160), Lara (6 660 + 3 110 з готелями), last minute (6 140), готелі (4 400), Rundreise (1 640), Antalya + last minute (800), дрібні Kappadokien/Istanbul/Schwarzmeer + Rundreise (220). Усі вже мають сторінку або матрицю (`/side`, `/antalya/lara`, `/last-minute`, `/hotels/turkei`, `/rundreisen`), тож хаб під них не оптимізуємо — лише лінки з блоку регіонів. Нових районів (Alanya, Kemer, Bodrum, Belek) у зібраній семантиці немає: щоб оцінити їх попит, запустіть режим extend-region (платно, з підтвердженням). Для нових зборів `collect.py` складає такі ключі в цей аркуш автоматично, а ядро з обсягом 10–50 понад ліміт — в аркуш «Довгий хвіст».

## Обмеження
- Нова видача перевірена вручну лише для одного ключа («türkei urlaub»).
- Класифікація посадкових робиться за URL і title, тож у ній є похибки (наприклад, «інше» 28 результатів); правила можна правити в `scripts/analyze.py`.
- Близько 90% пар ключів не мають спільних URL: SERP-кластеризація (hard-4: 63, soft-3: 56 кластерів) лишається лише довідкою.
- reisemu.de у ТОП-10 за жодним із 78 ключів не знайдено, відомі лише дві позиції 23 з Labs.
- Lara: SERP зібрано лише для 7 ключів (lara türkei, urlaub türkei lara, lara hotels, türkei hotel lara, liberty lara türkei, fame residence lara & spa türkei, türkei lara wetter); для решти ключів Lara сторінку призначено за рішенням власника, класифікація ТОП не проводилась.
- KD: для «2 wochen türkei rundreise» і «rundreise schwarzmeerküste türkei» значення не повернуто («н/д»); багато ключів мають KD 0, що може означати відсутність даних.
- Частотність і CPC з DataForSEO Labs (google.de). Переклади зроблено вручну за змістом, а не дослівно, примітки є для розмовних форм і неоднозначних слів.
