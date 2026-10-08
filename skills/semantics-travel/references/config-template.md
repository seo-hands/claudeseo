# Налаштування в CLAUDE.md

Один сайт - одна папка, окрема підпапка на кожний збір семантики (країна, курорт, готелі, тема). Налаштування лежать у двох секціях:

| Секція | Де | Що в ній |
|---|---|---|
| `## Дані сайту` | CLAUDE.md папки сайту (скрипти шукають у поточній папці, потім у батьківських угору до `E:\Work\claudeseo`; береться найближча, про кілька рівнів скрипт попереджає) | `site`, `market`, `language`, `location_code`, `se_domain`, `page_base` (базовий шлях турів), необов'язково `profile`, `brand`, `gsc`, `ga4` |
| `## semantics-travel` | CLAUDE.md **поточної** папки збору | `country`, `slug`, `page_base` (цільовий хаб; перекриває значення сайту) та решта ключів напрямку; у кінці підрозділ `### Журнал` |

Журнали (`### Журнал` у секціях `## semantics-travel` і `## tz-travel`) читаються й пишуться лише в CLAUDE.md поточної папки; якщо файла немає, він створюється. Рядки після `### Журнал` налаштуваннями не вважаються. Старий формат - усі ключі в одній секції `## semantics-travel` - теж працює. Перевірка: `python sp_common.py --workdir .`.

## Секція `## semantics-travel` (і ключі сайту)

Формат однаковий для обох секцій. Формат: рядки `- ключ: значення` (коментар після ` # `). Повторювані ключі: `region`, `existing_page`, `modifier_page`, `brand`, `exclude_product`, `business_rule`.

Обов'язкові: `site`, `country`, `slug`, `language`, `location_code`, `se_domain`, `page_base`, `scope_terms`.

### Межа збору: `scope_terms` (обов'язковий, лише в секції `## semantics-travel` папки напрямку)

`scope_terms: <слово теми>|<варіант написання>|...` - слова теми цього збору з варіантами написання (напр. `türkei|tuerkei|turkei|turkey`, `ägypten|aegypten|egypt`). З даних сайту ключ не успадковується; якщо його немає, усі скрипти зупиняються й просять його задати.

- Ключ вважається темою збору, лише якщо містить хоча б одне слово зі `scope_terms` (без урахування регістру, збіг за підрядком; кожне слово - regex, тож для коротких слів задавайте межі: `(?<![a-z])side(?![a-z])`).
- Ключ без жодного слова теми не йде ні в кластери, ні в «Розподіл по сторінках»: лише в аркуш «Напрямки розширення» з позначкою «поза межами збору» і частотністю.
- Регіони й типи турів усередині теми («ägypten urlaub hurghada», «ägypten last minute») лишаються в зборі: вони містять слово теми; матриця «регіон × тип туру» працює на них.
- Seed теж мусять містити слово теми: `--propose-seeds` пропонує лише такі, суміжні (курорти, інші продукти) показує окремим списком «не збирається, якщо не попросите» без оцінки вартості; `collect.py --seeds` із seed без слова теми зупиняється.
- Курорт чи іншу тему збирайте окремо, у власній підпапці зі своїм `scope_terms`. Ключі, додані свідомо через `add_region.py` (джерело `region:...`), межа не чіпає.
Необов'язкові: `profile` (профіль ринку, за замовчуванням за se_domain/мовою), `hotels_page`, `main_keyword`, `hub_slugs` (слаги країни в URL конкурентів, через `|`), `hub_extra_regex`, `region: <назва> = <regex по URL>`, `lemma_regions` (регіони з власними лемними кластерами, через `|`), `existing_page`, `modifier_page: <regex по ключу> = <сторінка>` (наявна посадкова сайту під модифікатор: місяць, ціна, місто вильоту; ключ, що за ТОП пішов би на хаб чи гайд Reisezeit, веде на неї), `brand` (regex), `exclude_product` (regex), `thr_ok` (5), `thr_disputed` (3), `max_keywords` (100), `business_rule`.

`business_rule: name=...; match=<regex по ключу>; family=<pauschal|lastminute|allinclusive|...>; page={page_base}/<сторінка>; exclude_region=yes; exclude_patterns=<regex1>||<regex2>; exceptions=<ключ1>||<ключ2>; note=<текст>`
Правило діє лише для ключів без назви регіону й без іншого головного типу туру (exclude_region + exclude_patterns).

## Шаблон

CLAUDE.md папки сайту (`example-com\CLAUDE.md`):

```markdown
## Дані сайту
- site: https://example.com                 # домен сайту
- market: Німеччина                         # ринок (країна пошуку)
- language: de
- location_code: 2276                       # Німеччина
- se_domain: google.de
- page_base: /reisen                        # базовий шлях турів; цільовий хаб задає напрямок
- profile: de                               # (необов'язково) профіль ринку scripts/profiles/<код>.json; за замовчуванням за se_domain/мовою
- gsc: https://example.com/                 # (необов'язково) ресурс Search Console
- ga4: properties/000000000                 # (необов'язково)
```

CLAUDE.md папки напрямку (`example-com\spanien\CLAUDE.md`):

```markdown
## semantics-travel
- country: Spanien                          # країна/тема мовою сайту
- slug: spanien                             # для імен файлів: semantics-<slug>.xlsx
- page_base: /reisen/spanien                # цільовий хаб напрямку на сайті
- scope_terms: spanien|spain|espana         # ОБОВ'ЯЗКОВО: межа збору - слова теми з варіантами написання
- hotels_page: /hotels/spanien              # (необов'язково) хаб готелів
- main_keyword: spanien urlaub              # (необов'язково) головний ключ для звірки видачі
- hub_slugs: spanien|espana                 # як країна пишеться в URL конкурентів
- region: mallorca = (?<![a-z])(mallorca|palma)(?![a-z])    # регіони: назва = regex по URL (можна кілька рядків)
- lemma_regions: mallorca|teneriffa         # (необов'язково) регіони, що утворюють власні лемні кластери
- existing_page: /reisen/spanien            # сторінки, що вже існують на сайті (кілька рядків)
- modifier_page: november = /reisen/spanien/november        # (необов'язково) наявна посадкова під модифікатор ключа (кілька рядків)
- brand: check24|holidaycheck|tui           # бренди конкурентів для фільтра (кілька рядків)
- exclude_product: flug|flüge               # (необов'язково) запити про інший продукт, який сайт не продає
- business_rule: name=pauschalreise; match=pauschalreisen?; family=pauschal; page={page_base}/pauschalreise; exclude_region=yes; exclude_patterns=last ?minute||all[ -]?inclusive.*pauschal; exceptions=pauschalreise mallorca spanien; note=Хаб не оптимізуємо під Pauschalreise

### Журнал
- збір — 2026-10-07; що зроблено, які файли

## tz-travel

### Журнал
```

Країни: Німеччина `location_code: 2276`, `se_domain: google.de`, `language: de`. Інші коди: DataForSEO Locations (для Австрії 2040/google.at, Швейцарії 2756/google.ch).
