# Ендпоінти, ціни й обмеження

Усі ендпоінти нижче використовувались у запусках 2026-10-08. Іншого не додавати без позначки «не перевірено». Ціни — фактичні, з полів `cost`, звірені з балансом; джерело для кошторису — `scripts/prices.json`. Змінилась ціна — онови `prices.json` і цю таблицю з новою датою.

## Ендпоінти за етапами

| Етап | Ендпоінт API | Ім'я в кеші | Параметри | Ціна (2026-10-08) |
|---|---|---|---|---|
| 0 | `dataforseo_labs/locations_and_languages` (GET) | `_labs\labs-locations_and_languages` | — | безкоштовно |
| 0–2 | `appendix/user_data` (GET) | не кешується | — | безкоштовно |
| 1 | `backlinks/bulk_spam_score/live` | `_list*\backlinks-bulk_spam_score` | `targets` — один запит на список | 0,024 $ + 0,000036 $ за домен |
| 1 | `backlinks/summary/live` | `backlinks-summary` | `include_subdomains`, `exclude_internal_backlinks` | 0,024036 $ |
| 1 | `dataforseo_labs/google/domain_rank_overview/live` | `labs-domain_rank_overview-<ринок>-<мова>` | `location_code`, `language_code`, `ignore_synonyms` | 0,01212 $ |
| 1 | той самий без `location_code` | `labs-domain_rank_overview-all` | лише `target` — розбивка за всіма ринками Labs | 0,0136–0,0233 $ (13–94 ринки) |
| 1 | `backlinks/referring_domains/live` для акцептора | `<акцептор>\backlinks-referring_domains` | `limit 1000`, `order_by rank,desc`, без фільтра | 0,06 $ за 1000 рядків |
| 1 | `backlinks/backlinks/live` | `backlinks-backlinks-to-acceptor` | `target` — акцептор, фільтр `domain_from = <донор>`, `limit 10` | 0,024036 $ |
| 1 | `serp/google/organic/task_post` → `task_get/advanced/<id>` | `serp-organic-task-<casino\|credit\|adv>` | `site:домен …`, `depth 10`, `location_code`, `se_domain` | 0,003 $ за запит |
| 2 | `backlinks/timeseries_summary/live` | `backlinks-timeseries_summary` | 12 місяців, `group_range month` | 0,024468 $ |
| 2 | `backlinks/referring_domains/live` для донора | `backlinks-referring_domains` | `limit 100`, `order_by rank,desc` | 0,0276 $ |
| 2 | `dataforseo_labs/google/historical_rank_overview/live` | `labs-historical_rank_overview-<ринок>-<мова>` | 13 місяців від `date_from`, домінантна мова | 0,1356 $ |
| 2 | `dataforseo_labs/google/ranked_keywords/live` | `labs-ranked_keywords-<ринок>-<мова>` | `limit 100`, сортування за трафіком | 0,024 $ |
| 2 | `backlinks/referring_domains/live` із фільтром зони | `backlinks-referring_domains-<зона>` | `filters domain like %<зона>`, `limit 30` | ≈0,025 $ |

Формули: Backlinks — 0,024 $ + 0,000036 $ за рядок; Labs — 0,012 $ + 0,00012 $ за рядок (historical — 0,12 $ + 0,0012 $ за місяць); SERP у черзі — 0,0006 $ за 10 результатів, оператор `site:` множить на 5.

Орієнтири на домен: етап 1 — ≈0,075 $; повний етап 2 — ≈0,21 $; скорочений (домен не з TLD ринку) — ≈0,05 $. Найдорожчий крок — `historical_rank_overview`.

Не потрібні: `backlinks_bulk_ranks` (ранг є в summary), `bulk_traffic_estimation` (немає розбивки за позиціями, `domain_rank_overview` дає те саме і більше), `domain_rank_overview` для окремого «основного ринку» не-TLD доменів (запит без `location_code` покриває всі ринки).

## SERP: чому `task_get/advanced`

У `semantics-travel` формат `advanced` заборонено: для ранжування на google.de він повертав видачу, яка не збігалась із реальною. Тут ця заборона не стосується: нам потрібні не позиції, а лише кількість результатів і список URL домену за запитом із `site:`. Склад топу за звичайним ключем ми не оцінюємо. Якщо скіл колись почне дивитись позиції — переходити на `regular` і перевіряти якість видачі, як у `semantics-travel`.

## Обмеження

- **Live-SERP** (`live/regular`, `live/advanced`) 2026-10-08 повертав помилку 50000 на будь-який запит; черга працює. Результат за 15–60 секунд, окремі завдання висять довше або не повертаються взагалі (оплачено, результату немає) — такі позначаються «не отримано».
- **Довгі запити з `site:`** (7 слів через OR) повертають сторонні сайти. Тільки короткі — по два терміни.
- **`depth 20` із `site:`** — друга десятка результатів чужа; досить `depth 10`.
- **Сторонні сайти у видачі** замість сторінок домену — «невизначено», не «чисто». Для Казахстану запит про казино дає це для більшості доменів.
- **Regex-фільтр у `referring_domains`** повертає 0 без помилки, і «немає збігів» не відрізнити від «фільтр не спрацював». Брати список за рангом і фільтрувати локально. Точний фільтр `=` у `backlinks_backlinks` і `like` у `referring_domains` працюють.
- **`limit 1000` у донорів акцептора** покриває всіх донорів з рангом вище нуля (їх зазвичай 200–300); донори з нульовим рангом можуть не потрапити.
- **Labs: Росії (2643) немає.** Загальний трафік російськомовних сайтів без неї занижений — так і писати.
- **Labs: мови.** Для Казахстану (2398) лише `ru`, `kk` немає; для України (2804) — `uk` і `ru`. `stage0.py` перевіряє це в довіднику.
- **Cloudflare:** частина сайтів віддає 403 і скрипту, і WebFetch — без повторних спроб, у «Ручну перевірку». Для таких сайтів поля Backlinks API про биті сторінки і зовнішні посилання недостовірні.
- **HTTP 500** від шлюзу API: клієнт повторює запит із паузою. Такий запит може бути списаний — звіряти баланс після етапу.
- **MCP DataForSEO** не повертає `cost` і не пише кеш — платні запити через нього не робити.
- **Тренди:** nofollow-донорів по всій базі стало у 2–4,6 раза більше за рік; dofollow-донори в більшості доменів падають з квітня 2026. Тому тренд — лише dofollow і лише відносно медіани списку.
