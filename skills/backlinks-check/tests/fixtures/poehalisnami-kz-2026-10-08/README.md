# Еталон: poehalisnami.kz, запуск 2026-10-08

Повний кеш запуску для офлайн-тестів (`tests/run_tests.py`, тести 1 і 2). Тести запускають скрипти з `--offline --cache-dir <ця папка>\cache`, тому TTL не враховується і платних запитів немає.

## Що тут сирі відповіді API

`cache\<домен>\<ендпоінт>-2026-10-08.json` — 84 файли, записані клієнтом DataForSEO без змін:

- `backlinks-summary`, `labs-domain_rank_overview-kz-ru`, три `serp-organic-task-*` — для всіх 10 доменів;
- `labs-domain_rank_overview-all` — для 6 доменів не з `.kz`;
- `backlinks-timeseries_summary`, `backlinks-referring_domains` — для 7 кандидатів;
- `labs-historical_rank_overview-kz-ru`, `labs-ranked_keywords-kz-ru` — для 4 кандидатів з `.kz`;
- `ng.kz\backlinks-backlinks-to-acceptor`, `ng.kz\backlinks-referring_domains-webapp`;
- `poehalisnami.kz\backlinks-referring_domains` (1000 донорів акцептора);
- `_list\`, `_list2\` — `backlinks-bulk_spam_score` двома запитами (6 і 4 домени);
- `_labs\labs-locations_and_languages` — безкоштовний довідник Labs.

`lifepvl.kz\serp-organic-task-adv` у запуску не повернувся з черги; дозапитаний того ж дня (0,003 $) уже скриптом скіла. Файли `labs-domain_rank_overview-ua-ru` (зайвий запит запуску) і відповіді з помилками сюди не скопійовано.

Перед копіюванням перевірено: значень із `dataforseo.env` у файлах немає, e-mail-подібних рядків у відповідях API — 0.

## Що тут не сирі відповіді API

- `cache\<домен>\pages\<md5 URL>.html` — 34 сторінки сайтів, завантажені безкоштовно (статті, списки рекламних розділів, головні). Статті й списки — із запуску; головні сторінки кандидатів завантажено того ж дня пізніше, уже скриптом `fetch_pages.py`. У копіях вирізано `<script>`, `<style>`, `<svg>` і коментарі, а e-mail-адреси замінено на `[email]` (49 замін) — на розбір посилань це не впливає.
- `run\input.md` — вхідні дані запуску у форматі скіла.
- `run\site-notes.json` — **відтворено з розмови**: тематика, рубрика подорожей, рекламний розділ, мова, регіон і аудиторія — це результати WebFetch головних сторінок, які в запуску існували лише в чаті; список статей для розбору і записи ручної перевірки — рішення, прийняті в запуску.
- `run\verdicts.json` — вердикти, причини й рекомендації у фінальному вигляді, прийнятому замовником (включно з ручною заміною: #5 socportal.info, #6 tourlib.net, резерв lifepvl.kz). Тому тест 2 очікувано показує три розбіжності з `recommendation_auto`; розбіжностей `verdict` / `verdict_auto` немає.
- `run\ledger-original.json` — лог `cost` оригінального запуску (для довідки; тест його не читає).
- `expected.json` — числа аркуша «Зведена» з прийнятого файла `backlinks\donors-poehalisnami-kz-2026-10-08.xlsx`; з ними тест 2 порівнює результат.

## Чого тут немає

Балансу запуску (46,246346 → 44,481194 $, витрата 1,765 $) — він записаний у `backlinks\notes-backlinks-check.md` і в константі `ACTUAL_SPEND_KZ` тесту 1.
