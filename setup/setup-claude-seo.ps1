# Розгортання робочого простору claudeseo на новому ПК (Windows, PowerShell 5.1+).
# Запуск:  powershell -ExecutionPolicy Bypass -File setup-claude-seo.ps1 [-Root E:\Work\claudeseo]
# Скрипт можна запускати повторно: готові кроки він пропускає.
# У скрипті НЕМАЄ паролів, ключів і логінів: облікові дані читаються під час запуску з ~\.config\claude-seo\.
param(
    [string]$Root = 'E:\Work\claudeseo',
    [string]$RepoUrl = 'https://github.com/seo-hands/claudeseo.git'
)
$ErrorActionPreference = 'Stop'
$ClaudeDir  = Join-Path $env:USERPROFILE '.claude'
$SecretsDir = Join-Path $env:USERPROFILE '.config\claude-seo'
$Skills     = @('semantics-travel', 'tz-travel')
$Marketplace = 'AgriciDaniel/claude-seo'                       # джерело плагіна на GitHub
$Plugins     = @('claude-seo@agricidaniel-claude-seo', 'seo-cockpit@agricidaniel-claude-seo')
$McpPackage  = 'dataforseo-mcp-server@2.8.10'
$McpModules  = 'SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION'
$EmbedModel  = 'jinaai/jina-embeddings-v2-base-de'

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  OK: $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  УВАГА: $text" -ForegroundColor Yellow }
function Quiet {
    # тихий запуск: помилки й stderr не зупиняють скрипт, результат — стандартний вивід
    param([string]$Exe, [string[]]$Arguments)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $Exe @Arguments 2>$null
    $ErrorActionPreference = $old
    return $out
}
function Run {
    # запуск зовнішньої програми з перевіркою коду завершення
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Команда завершилась з помилкою ($LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

# ---------- 1. Node, Git, Claude Code ----------
Step '1. Перевірка Node.js, Git і Claude Code'
$missing = @()
if (Get-Command node -ErrorAction SilentlyContinue) { Ok ("Node.js " + (node --version)) }
else { $missing += 'Node.js LTS:   winget install OpenJS.NodeJS.LTS' }
if (Get-Command git -ErrorAction SilentlyContinue) { Ok (git --version) }
else { $missing += 'Git:           winget install Git.Git' }
if (Get-Command claude -ErrorAction SilentlyContinue) { Ok ("Claude Code " + (claude --version)) }
else { $missing += 'Claude Code:   npm install -g @anthropic-ai/claude-code   (потім запустіть claude і увійдіть)' }
if ($missing.Count -gt 0) {
    Warn 'Не знайдено потрібних програм. Встановіть їх, відкрийте нове вікно PowerShell і запустіть скрипт ще раз:'
    $missing | ForEach-Object { Write-Host "    $_" }
    exit 1
}

# ---------- 2. Python 3.12 ----------
Step '2. Пошук python.exe 3.12'
$Python = $null
$candidates = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $found = Quiet py @('-3.12', '-c', 'import sys; print(sys.executable)')
    if ($LASTEXITCODE -eq 0 -and $found) { $candidates += ([string]$found).Trim() }
}
$candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
$candidates += 'C:\Program Files\Python312\python.exe'
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { $candidates += $cmd.Source }
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c) -and ($c -notlike '*WindowsApps*')) {
        $ver = Quiet $c @('-c', 'import sys; print(str(sys.version_info[0]) + chr(46) + str(sys.version_info[1]))')
        if ($ver -eq '3.12') { $Python = $c; break }
    }
}
if (-not $Python) {
    Warn 'Python 3.12 не знайдено. Встановіть:  winget install Python.Python.3.12  — і запустіть скрипт ще раз.'
    exit 1
}
Ok "Python 3.12: $Python"

# ---------- 3. Репозиторій ----------
Step "3. Репозиторій у $Root"
if (Test-Path (Join-Path $Root '.git')) {
    Run git @('-C', $Root, 'pull', '--ff-only')
    Ok 'репозиторій оновлено (git pull)'
}
elseif ((Test-Path $Root) -and (Get-ChildItem $Root -Force | Select-Object -First 1)) {
    throw "Папка $Root існує, не порожня і не є репозиторієм. Перейменуйте її або задайте інший шлях параметром -Root."
}
else {
    # якщо GitHub попросить увійти — відкриється вікно браузера
    Run git @('clone', $RepoUrl, $Root)
    Ok 'репозиторій клоновано'
}
if ($Root -ne 'E:\Work\claudeseo') {
    # скіли шукають дані сайту вгору до цієї папки; за замовчуванням це E:\Work\claudeseo
    [Environment]::SetEnvironmentVariable('CLAUDE_SEO_PROJECTS_ROOT', $Root, 'User')
    $env:CLAUDE_SEO_PROJECTS_ROOT = $Root
    Warn "Корінь не стандартний: змінну CLAUDE_SEO_PROJECTS_ROOT встановлено в $Root. У tz-config.json проєктів задайте models_dir: $Root\models"
}

# ---------- 4. Посилання (junction) на скіли ----------
Step '4. Скіли в ~\.claude\skills'
$skillsDir = Join-Path $ClaudeDir 'skills'
New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null
foreach ($name in $Skills) {
    $link = Join-Path $skillsDir $name
    $target = Join-Path $Root "skills\$name"
    if (-not (Test-Path $target)) { throw "У репозиторії немає $target" }
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction') {
            if (($item.Target | Select-Object -First 1) -eq $target) { Ok "$name — посилання вже є"; continue }
            cmd /c rmdir "$link" | Out-Null          # знімаємо лише посилання, вміст цільової папки не чіпаємо
        }
        else {
            # справжня папка зі старою копією скіла: не видаляємо, а перейменовуємо
            $bak = "$link.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
            Rename-Item -Path $link -NewName (Split-Path $bak -Leaf)
            Warn "стару папку $name перейменовано на $(Split-Path $bak -Leaf)"
        }
    }
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Ok "$name -> $target"
}

# ---------- 5. Плагін claude-seo (marketplace) ----------
Step '5. Плагін claude-seo'
$known = (& claude plugin marketplace list) -join "`n"
if ($known -notmatch 'agricidaniel-claude-seo|AgriciDaniel/claude-seo') { Run claude @('plugin', 'marketplace', 'add', $Marketplace) }
$installedFile = Join-Path $ClaudeDir 'plugins\installed_plugins.json'
$installed = ''
if (Test-Path $installedFile) { $installed = Get-Content $installedFile -Raw }
foreach ($p in $Plugins) {
    if ($installed -match [regex]::Escape($p)) { Ok "$p — уже встановлено" }
    else { Run claude @('plugin', 'install', $p); Ok "$p встановлено" }
}
# власне середовище плагіна (venv + браузер для render_page.py)
$runtime = Get-ChildItem (Join-Path $ClaudeDir 'plugins\cache') -Recurse -Filter runtime.py -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like '*claude-seo*\scripts\runtime.py' } | Sort-Object FullName -Descending | Select-Object -First 1
if ($runtime) { Run $Python @($runtime.FullName, 'setup'); Ok 'середовище плагіна готове' }
else { Warn 'runtime.py плагіна не знайдено: відкрийте Claude Code, перевірте /plugin і запустіть скрипт ще раз' }

# ---------- 6. Пакети Python для скілів ----------
Step '6. Пакети Python'
Run $Python @('-m', 'pip', 'install', '--upgrade', 'fastembed', 'python-docx', 'openpyxl', 'beautifulsoup4', 'numpy')
Ok 'fastembed, python-docx, openpyxl, beautifulsoup4, numpy'

# ---------- 7. Секрети (кладе людина, не скрипт) ----------
Step "7. Секрети в $SecretsDir"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
$fieldCfg = Join-Path $SecretsDir 'dataforseo-field-config.json'
if (-not (Test-Path $fieldCfg)) { Copy-Item (Join-Path $Root 'setup\dataforseo-field-config.json') $fieldCfg }   # не секрет: фільтр полів MCP
$notSecrets = @('google-api.json', 'dataforseo-field-config.json', 'dataforseo-ledger.json')
while ($true) {
    $need = @()
    if (-not (Test-Path (Join-Path $SecretsDir 'dataforseo.env'))) { $need += 'dataforseo.env  (рядки DATAFORSEO_LOGIN=... і DATAFORSEO_PASSWORD=...)' }
    if (-not (Test-Path (Join-Path $SecretsDir 'google-api.json'))) { $need += 'google-api.json (ключ Google API і шлях до файла сервісного акаунта)' }
    $sa = Get-ChildItem $SecretsDir -Filter *.json | Where-Object { $notSecrets -notcontains $_.Name }
    if (-not $sa) { $need += 'JSON сервісного акаунта Google (файл, на який посилається google-api.json)' }
    if ($need.Count -eq 0) { break }
    Warn "Покладіть у $SecretsDir такі файли (зі старого ПК або з менеджера паролів):"
    $need | ForEach-Object { Write-Host "    - $_" }
    Read-Host '  Коли файли на місці, натисніть Enter (Ctrl+C — перервати)' | Out-Null
}
Ok 'dataforseo.env, google-api.json і JSON сервісного акаунта на місці'

# ---------- 8. MCP DataForSEO ----------
Step '8. MCP DataForSEO'
Quiet claude @('mcp', 'get', 'dataforseo') | Out-Null
if ($LASTEXITCODE -eq 0) { Ok 'MCP dataforseo вже налаштовано' }
else {
    # облікові дані беруться з dataforseo.env під час запуску і на екран не виводяться
    $envValues = @{}
    foreach ($line in Get-Content (Join-Path $SecretsDir 'dataforseo.env')) {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $envValues[$Matches[1]] = $Matches[2].Trim('"').Trim("'") }
    }
    if (-not $envValues['DATAFORSEO_LOGIN'] -or -not $envValues['DATAFORSEO_PASSWORD']) { throw 'У dataforseo.env немає DATAFORSEO_LOGIN або DATAFORSEO_PASSWORD' }
    $mcpArgs = @('mcp', 'add', 'dataforseo', '-s', 'user',
        '-e', ('DATAFORSEO_USERNAME=' + $envValues['DATAFORSEO_LOGIN']),
        '-e', ('DATAFORSEO_PASSWORD=' + $envValues['DATAFORSEO_PASSWORD']),
        '-e', "ENABLED_MODULES=$McpModules",
        '-e', "FIELD_CONFIG_PATH=$fieldCfg",
        '--', 'cmd', '/c', 'npx', '-y', $McpPackage)
    & claude @mcpArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Не вдалося додати MCP dataforseo (claude mcp add)' }
    Ok "MCP dataforseo додано ($McpPackage)"
}

# ---------- 9. Налаштування seo-cockpit у settings.json ----------
Step '9. Налаштування seo-cockpit'
$settingsFile = Join-Path $ClaudeDir 'settings.json'
$template = Get-Content (Join-Path $Root 'setup\settings.seo-cockpit.template.json') -Raw
$template = $template.Replace('{{PYTHON}}', $Python.Replace('\', '\\')).Replace('{{ROOT}}', $Root.Replace('\', '\\'))
$tpl = $template | ConvertFrom-Json
if (Test-Path $settingsFile) {
    Copy-Item $settingsFile ("$settingsFile.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json
}
else { $settings = New-Object PSObject }
if (-not $settings.PSObject.Properties['pluginConfigs']) { $settings | Add-Member -NotePropertyName pluginConfigs -NotePropertyValue (New-Object PSObject) }
foreach ($prop in $tpl.pluginConfigs.PSObject.Properties) {
    $settings.pluginConfigs | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
}
# без BOM: Claude Code читає settings.json як звичайний UTF-8
[IO.File]::WriteAllText($settingsFile, ($settings | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding($false)))
Ok "settings.json оновлено (python і auditsFolder підставлено)"

# ---------- 10. Модель ембедінгів ----------
Step '10. Модель ембедінгів'
$modelsDir = Join-Path $Root 'models'
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
$env:CLAUDESEO_MODELS_DIR = $modelsDir
$env:CLAUDESEO_EMBED_MODEL = $EmbedModel
# перший раз завантажує близько 0,6 ГБ з HuggingFace; далі бере з папки
Run $Python @('-c', "import os; from fastembed import TextEmbedding; TextEmbedding(model_name=os.environ['CLAUDESEO_EMBED_MODEL'], cache_dir=os.environ['CLAUDESEO_MODELS_DIR']); print('model ok')")
Ok "$EmbedModel у $modelsDir"

# ---------- 11. Перевірка ----------
Step '11. Перевірка: налаштування reisemu-de\turkei'
Run $Python @('-X', 'utf8', (Join-Path $Root 'skills\semantics-travel\scripts\sp_common.py'), '--workdir', (Join-Path $Root 'reisemu-de\turkei'))
Write-Host "`nГотово. Відкрийте Claude Code у папці збору, напр.:  cd $Root\reisemu-de\turkei ; claude" -ForegroundColor Green
