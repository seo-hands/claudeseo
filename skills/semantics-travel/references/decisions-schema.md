# semantics-decisions.json (ручні рішення, керуються `apply_decisions.py`)

```json
{
  "business_rules":      [{"name","match","family","page","exclude_region","exclude_patterns","exceptions","note"}],
  "keyword_overrides":   {"<ключ>": {"page": "/шлях", "reason": "..."}},           // «за рішенням власника»
  "contested_verdicts":  {"/сторінка": {"verdict": "окрема|фільтр", "reason": "..."}},
  "manual_check":        {"<ключ>": "причина"},                                    // «перевірити вручну»
  "page_notes":          {"/сторінка": "примітка для аркуша «Розподіл по сторінках»"},
  "known_positions":     {"<ключ>": "23 (Labs)"},                                  // позиція сайту поза ТОП-10
  "manual_filter":       {"<ключ>": "причина"},                                    // у «Відфільтровані»
  "page_overrides":      {"<ключ>": "/матриця"},                                   // поле page_override у keywords.json
  "region_pages":        {"<регіон>": "/сторінка регіону"},
  "serp_manual_check":   {"keyword": "<головний ключ>", "domains": ["домен1", "домен2"]}   // реальний ТОП з браузера
}
```
Бізнес-правила з CLAUDE.md та з цього файлу додаються. Рішення переживають будь-який recluster.
