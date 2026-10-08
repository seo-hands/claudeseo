# reisemu.de · Туреччина

Напрямок: Туреччина (Türkei). Цільовий хаб: https://reisemu.de/tour/turkei. Дані сайту (домен, мова, location_code, se_domain, GSC, GA4) — у CLAUDE.md батьківської папки.

## semantics-travel
- country: Türkei
- slug: turkei
- page_base: /tour/turkei
- scope_terms: türkei|tuerkei|turkei|turkey
- hotels_page: /hotels/turkei
- main_keyword: türkei urlaub
- hub_slugs: tuerkei|turkei|türkei|tuerkei-co4|ferienreisen-tuerkei|tr_tuerkei|tuerkei-urlaub
- hub_extra_regex: riviera|aegaeis|region/?$|/urlaub/tuerkei/(inland|[a-z-]*region)|tuerkei-urlaub-buchen|tuerkei/billigurlaub
- lemma_regions: side|antalya
- region: antalya = (?<![a-z])(antalya|lara|kundu|belek)(?![a-z])
- region: side = (?<![a-z])(side|manavgat|colakli)(?![a-z])
- region: alanya = (?<![a-z])(alanya|avsallar|konakli|okurcalar|mahmutlar|incekum)(?![a-z])
- region: kemer = (?<![a-z])(kemer|tekirova|goynuk)(?![a-z])
- region: bodrum = (?<![a-z])(bodrum|turgutreis|gumbet)(?![a-z])
- region: marmaris = (?<![a-z])(marmaris|icmeler)(?![a-z])
- region: fethiye = (?<![a-z])(fethiye|oeluedeniz|oludeniz|calis)(?![a-z])
- region: istanbul = (?<![a-z])istanbul(?![a-z])
- region: kappadokien = kappadok|cappadoc
- region: didim = (?<![a-z])didim(?![a-z])
- region: kusadasi = (?<![a-z])kusadasi(?![a-z])
- region: izmir = (?<![a-z])izmir(?![a-z])
- region: schwarzmeer = schwarzmeer
- existing_page: /tour/turkei
- existing_page: /tour/turkei/all-inclusive
- existing_page: /tour/turkei/side
- existing_page: /tour/turkei/antalya
- business_rule: name=pauschalreise; match=pauschalreisen?; family=pauschal; page={page_base}/pauschalreise; exclude_region=yes; exclude_patterns=last ?minute||all[ -]?inclusive.*pauschal; note=Хаб не оптимізуємо під Pauschalreise: ключі з «Pauschalreise/Pauschalreisen» без регіону й без іншого головного типу туру ведуть на /tour/turkei/pauschalreise.

### Журнал
- збір — 2026-10-07; keywords.json: 131 ключ (77 основних + ключі Lara); SERP live/regular зібрано 7 жовтня 2026 (serp-raw-regular, 78 ключів); попит по Lara — lara-demand.json
- розподіл — 2026-10-08; semantics-turkei.xlsx, recommendations-turkei.md: 119 ключів у 26 кластерах, 14 сторінок у розподілі; ручні рішення — semantics-decisions.json

## tz-travel

### Журнал
- /tour/turkei — 2026-10-08; файли: meta-turkei.xlsx, tz-copywriter-turkei.docx; конкуренти (11): schauinsland-reisen.de, neckermann-reisen.de, sonnenklar.tv, anextour.de, aldi-reisen.de, restplatzboerse.com, urlaub.check24.de, holidayplatz.de, oeger.de, travelantis.de, lidl-reisen.de
