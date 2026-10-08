# claudeseo

Робочий простір SEO-проєктів для Claude Code: власні скіли, дані зборів семантики по сайтах і скрипт розгортання на новому ПК.

## Що тут є

| Папка | Зміст |
|---|---|
| `skills\semantics-travel\` | Скіл етапу 1: збір ключів, кластери, розподіл по сторінках (DataForSEO) |
| `skills\tz-travel\` | Скіл етапу 2: мета-теги й ТЗ для копірайтера (без DataForSEO) |
| `setup\` | Скрипт розгортання, шаблон налаштувань seo-cockpit, конфіг полів DataForSEO MCP |
| `reisemu-de\` | Сайт reisemu.de; `turkei\` — Туреччина (етапи 1–2), `aegypten\` — заготовка |
| `ContentOptimization\` | Чернетки промптів |

Не в репозиторії (див. `.gitignore`): `models\` (модель ембедінгів, 615 МБ — завантажується скриптом), `_backup\` (локальні архіви), секрети.

## Структура папок

Один сайт — одна папка. Кожний збір семантики (країна, курорт, готелі, тема без країни) — окрема підпапка, глибина довільна:

```
reisemu-de\              CLAUDE.md: «## Дані сайту» (домен, мова, location_code, se_domain, GSC, GA4)
├─ turkei\               CLAUDE.md: «## semantics-travel» (налаштування напрямку + журнал), «## tz-travel» (журнал)
│  ├─ hotels\            майбутні збори всередині напрямку
│  └─ side\
├─ aegypten\
└─ familienurlaub\
```

Скіли запускаються з підпапки збору (`--workdir .`). Дані сайту вони шукають у CLAUDE.md поточної папки, потім у батьківських; журнали пишуть лише в CLAUDE.md поточної папки. Перевірити, що бачать скрипти:

```
python skills\semantics-travel\scripts\sp_common.py --workdir reisemu-de\turkei
```

## Розгортання на новому ПК

1. Встановіть Git, Node.js LTS, Python 3.12 і Claude Code (`npm install -g @anthropic-ai/claude-code`), увійдіть у Claude Code.
2. Завантажте з GitHub файл `setup\setup-claude-seo.ps1` і запустіть у PowerShell:
   `powershell -ExecutionPolicy Bypass -File setup-claude-seo.ps1 -Root E:\Work\claudeseo`
   Скрипт клонує репозиторій, створить посилання на скіли в `~\.claude\skills`, встановить плагін claude-seo, пакети Python і модель ембедінгів.
3. Коли скрипт зупиниться й попросить секрети — покладіть їх у `~\.config\claude-seo\` і натисніть Enter. Наприкінці скрипт покаже налаштування `reisemu-de\turkei` — це ознака, що все працює.

## Секрети

У репозиторії їх немає і не має бути. Вони лежать у `C:\Users\<користувач>\.config\claude-seo\`:

- `dataforseo.env` — `DATAFORSEO_LOGIN` і `DATAFORSEO_PASSWORD`;
- `google-api.json` — ключ Google API і шлях до файла сервісного акаунта;
- JSON сервісного акаунта Google (Search Console, GA4).

Переносьте їх між ПК вручну (менеджер паролів, флешка), не поштою і не через git. Сторінки конкурентів у `competitors-raw\` скіл зберігає вже без рядків, схожих на ключі.

## Щоденна робота

- Перед початком: `git pull`.
- Працюйте в Claude Code з папки збору (напр. `reisemu-de\turkei`).
- Наприкінці етапу скажіть Claude: «закоміть зміни і відправ на GitHub» — або вручну: `git add -A`, `git commit -m "…"`, `git push`.
- Скіли в `~\.claude\skills` — це посилання на `skills\` у цьому репозиторії: правки скілів теж комітяться тут.
