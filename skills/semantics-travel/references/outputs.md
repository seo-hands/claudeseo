# Вихідні файли

| Файл | Зміст |
|---|---|
| semantics-<slug>.xlsx | Увага; Ключі; Кластери; Типи посадкових конкурентів; Матриця типів по ключах; Готелі <регіон>; Напрямки розширення; Довгий хвіст (якщо є ядро понад ліміт); Відфільтровані; Конкуренти; Розподіл по сторінках; Перевірка спірних; Перетини між кластерами; SERP hard-4/soft-3 (довідка) |
| keywords.json | ключі (volume, cpc, intent, kd, source, translation_uk, ext_group, page_override) + `filtered` з причинами |
| serp-raw-regular/ | сирі відповіді SERP (по файлу на ключ) |
| serp-data.json | ТОП-10 по ключах з типом/регіоном/сторінкою-кандидатом |
| landing-verification.json | результати перевірки спірних пар |
| semantics-decisions.json | ручні рішення |
| clusters.json | кластери, рішення по ключах, типи (вхід для report.py, verify_landings.py, compare_methods.py) |
| cluster-map.html | карта кластерів |
| recommendations-<slug>.md | таблиці (report.py) + 5-7 рекомендацій |
| region-<slug>-demand.json, region-<slug>-raw/ | попит по регіону |
| batch-summary.xlsx, pages/ | CSV-пакет |
