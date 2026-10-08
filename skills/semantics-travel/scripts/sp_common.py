#!/usr/bin/env python3
"""Shared helpers of the semantics-travel skill: settings from CLAUDE.md, market profiles, DataForSEO client, cost guard, decisions file.

Nothing here prints credentials.  Settings come from two places (one site = one folder, one sub-folder per collection):
  * site data  — section "## Дані сайту" of the nearest CLAUDE.md: the working folder first, then its parents up to PROJECTS_ROOT;
  * direction  — section "## semantics-travel" of CLAUDE.md in the working folder only (keys of the direction + "### Журнал").
Journals ("### Журнал" inside "## semantics-travel" / "## tz-travel") are read and written only in the working folder's CLAUDE.md.
An old single-file layout (everything inside "## semantics-travel") keeps working.
"""
import base64, collections, hashlib, importlib.util, json, os, re, sys, unicodedata, urllib.request, urllib.error
from urllib.parse import urlsplit

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.expanduser("~/.config/claude-seo/dataforseo.env")

# Known prices (USD, upper bounds seen in practice) used for estimates.  Only endpoints with known price are used.
PRICES = {
    "serp_live_regular": 0.002,          # /serp/google/organic/live/regular, one keyword, depth 10
    "labs_ranked_keywords": 0.05,        # /dataforseo_labs/google/ranked_keywords/live (ledger upper bound)
    "labs_keyword_suggestions": 0.05,    # observed 0.024 for 100 items
    "labs_related_keywords": 0.05,       # observed 0.013 for 6-8 items
    "labs_bulk_keyword_difficulty": 0.01,
    "ads_search_volume": 0.075,          # approximate, confirm before use
}
OVER_LIMIT = 0.30                         # stop when real cost exceeds the estimate by more than 30 %

REQUIRED = ["site", "country", "slug", "language", "location_code", "se_domain", "page_base"]

CONFIG_TEMPLATE = """# CLAUDE.md папки САЙТУ (напр. E:\\Work\\claudeseo\\example-com\\CLAUDE.md) — дані сайту, спільні для всіх напрямків
## Дані сайту
- site: https://example.com                 # домен сайту
- market: Німеччина                         # ринок (країна пошуку)
- language: de
- location_code: 2276                       # Німеччина
- se_domain: google.de
- page_base: /reisen                        # базовий шлях турів на сайті; напрямок задає власний хаб
- profile: de                               # (необов'язково) профіль ринку scripts/profiles/<код>.json
- brand: check24|holidaycheck|tui           # (необов'язково) бренди конкурентів для фільтра
- gsc: https://example.com/                 # (необов'язково) ресурс Search Console
- ga4: properties/000000000                 # (необов'язково)

# CLAUDE.md папки НАПРЯМКУ (напр. ...\\example-com\\spanien\\CLAUDE.md) — налаштування збору й журнал
## semantics-travel
- country: Spanien                          # країна/тема мовою сайту
- slug: spanien                             # для імен файлів: semantics-<slug>.xlsx
- page_base: /reisen/spanien                # цільовий хаб напрямку на сайті
- scope_terms: spanien|spain|espana         # ОБОВ'ЯЗКОВО: межа збору - слова теми з варіантами написання; ключ без жодного з них у збір не йде
- hotels_page: /hotels/spanien              # (необов'язково) хаб готелів
- main_keyword: spanien urlaub              # (необов'язково) головний ключ для звірки видачі
- hub_slugs: spanien|espana                 # як країна пишеться в URL конкурентів
- region: mallorca = (?<![a-z])(mallorca|palma)(?![a-z])    # регіони: назва = regex по URL (можна кілька рядків)
- lemma_regions: mallorca|teneriffa         # (необов'язково) регіони, що утворюють власні лемні кластери
- existing_page: /reisen/spanien            # сторінки, що вже існують на сайті (кілька рядків)
- modifier_page: november = /reisen/spanien/november    # (необов'язково) наявна посадкова сайту під модифікатор ключа (місяць, ціна, місто вильоту): regex по ключу = сторінка
- exclude_product: flug|flüge               # (необов'язково) запити про інший продукт, який сайт не продає
- business_rule: name=pauschalreise; match=pauschalreisen?; family=pauschal; page={page_base}/pauschalreise; exclude_region=yes; exclude_patterns=last ?minute||all[ -]?inclusive.*pauschal; note=Хаб не оптимізуємо під Pauschalreise

### Журнал
"""


class ConfigMissing(Exception):
    pass


class Settings(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)


def _clean(v):
    return re.sub(r"\s+#\s.*$", "", v).strip()


PROJECTS_ROOT = os.environ.get("CLAUDE_SEO_PROJECTS_ROOT", "E:/Work/claudeseo")   # the upward search for site data stops below this folder
SITE_HEADING = r"(?:дані сайту|site data|site)\s*$"
DIRECTION_HEADING = r"semantics-(?:travel|pages)\b"
JOURNAL_HEADING = "Журнал"
LIST_KEYS = ("existing_pages", "brands", "exclude_products", "business_rules", "modifier_pages")


def _section(lines, heading_rx):
    """body lines of the first section whose heading matches, or None"""
    start, level = None, 0
    for i, l in enumerate(lines):
        m = re.match(r"^(#{1,6})\s*" + heading_rx, l.strip(), re.I)
        if m:
            start, level = i, len(m.group(1))
            break
    if start is None:
        return None
    body = []
    for l in lines[start + 1:]:
        m = re.match(r"^(#{1,6})\s", l)
        if m and len(m.group(1)) <= level:
            break
        body.append(l)
    return body


def _parse_body(body):
    d = {"regions": collections.OrderedDict(), "existing_pages": [], "brands": [], "exclude_products": [], "business_rules": [], "modifier_pages": []}
    for l in body:
        if re.match(r"^#{1,6}\s*" + JOURNAL_HEADING, l.strip(), re.I):
            break                      # the journal of the section is not settings
        l = l.strip().lstrip("-*").strip()
        if not l or ":" not in l or l.startswith("#"):
            continue
        k, v = l.split(":", 1)
        k, v = k.strip().lower(), _clean(v)
        if k == "region":
            name, rx = v.split("=", 1)
            d["regions"][name.strip()] = rx.strip()
        elif k == "existing_page":
            d["existing_pages"].append(v)
        elif k == "modifier_page":      # existing landing page of the site for a keyword modifier: <regex over the keyword> = <page>
            rx, page = v.rsplit("=", 1)
            d["modifier_pages"].append([rx.strip(), page.strip()])
        elif k == "brand":
            d["brands"].append(v)
        elif k == "exclude_product":
            d["exclude_products"].append(v)
        elif k == "business_rule":
            rule = {}
            for part in v.split(";"):
                if "=" in part:
                    a, b = part.split("=", 1)
                    rule[a.strip()] = b.strip()
            rule["exclude_region"] = rule.get("exclude_region", "no").lower() in ("yes", "true", "1")
            rule["exclude_patterns"] = [x for x in rule.get("exclude_patterns", "").split("||") if x]
            rule["exceptions"] = [x for x in rule.get("exceptions", "").split("||") if x]
            d["business_rules"].append(rule)
        elif v:
            d[k] = v
    return d


def parse_claude_md(path, heading_rx=DIRECTION_HEADING):
    """settings of one section of one CLAUDE.md (default: the direction section "## semantics-travel")"""
    body = _section(open(path, encoding="utf-8").read().split("\n"), heading_rx)
    if body is None:
        raise ConfigMissing("section")
    return _parse_body(body)


def find_site_data(workdir):
    """[(CLAUDE.md path, settings)] with a "## Дані сайту" section: the working folder first, then parents up to PROJECTS_ROOT"""
    found, cur = [], os.path.abspath(workdir)
    root = os.path.normcase(os.path.abspath(PROJECTS_ROOT))
    for _ in range(8):
        if os.path.normcase(cur) == root:
            break
        f = os.path.join(cur, "CLAUDE.md")
        if os.path.exists(f):
            try:
                found.append((f, parse_claude_md(f, SITE_HEADING)))
            except ConfigMissing:
                pass
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return found


def load_settings(workdir=".", claude_md=None):
    """Site data (nearest "## Дані сайту" upwards) merged with the direction section of the working folder; the direction wins."""
    path = claude_md or os.path.join(workdir, "CLAUDE.md")
    direction = None
    if os.path.exists(path):
        try:
            direction = parse_claude_md(path)
        except ConfigMissing:
            direction = None
    sites = find_site_data(os.path.dirname(os.path.abspath(path)) if claude_md else workdir)
    if direction is None and not sites:
        raise ConfigMissing(f"у {path} немає секції «## semantics-travel», а в цій папці та батьківських (до {PROJECTS_ROOT}) немає секції «## Дані сайту»")
    notes = []
    d = {"regions": collections.OrderedDict(), "existing_pages": [], "brands": [], "exclude_products": [], "business_rules": [], "modifier_pages": []}
    if sites:
        d.update({k: v for k, v in sites[0][1].items() if k not in LIST_KEYS + ("regions",)})
        d["regions"].update(sites[0][1]["regions"])
        for k in LIST_KEYS:
            d[k] += sites[0][1][k]
        if len(sites) > 1:
            notes.append("дані сайту знайдено на кількох рівнях: взято найближчий " + sites[0][0] + "; проігноровано " + ", ".join(f for f, _ in sites[1:]))
    if direction:
        if sites and "page_base" not in direction and d.get("page_base"):
            notes.append(f"page_base успадковано з даних сайту ({d['page_base']}): задайте цільовий хаб напрямку в секції «## semantics-travel» цієї папки")
        d.update({k: v for k, v in direction.items() if k not in LIST_KEYS + ("regions",)})
        d["regions"].update(direction["regions"])
        for k in LIST_KEYS:
            d[k] += direction[k]
    elif sites:
        notes.append(f"у {path} немає секції «## semantics-travel»: напрямок не налаштовано, є лише дані сайту")
    missing = [k for k in REQUIRED if not d.get(k)]
    if missing:
        where = (" (дані сайту: " + sites[0][0] + ")") if sites else ""
        raise ConfigMissing("не вистачає налаштувань: " + ", ".join(missing) + where + ". Ключі сайту (site, language, location_code, se_domain) — у секції «## Дані сайту», "
                            "ключі напрямку (country, slug, page_base) — у секції «## semantics-travel» CLAUDE.md поточної папки")
    # collection boundary: mandatory in the DIRECTION section (never inherited from the site data)
    terms = [t.strip() for t in (direction or {}).get("scope_terms", "").split("|") if t.strip()]
    if not terms:
        raise ConfigMissing(f"не задано межу збору: у секції «## semantics-travel» файла {path} немає ключа scope_terms. Додайте рядок "
                            "«- scope_terms: <слово теми>|<варіант написання>|...» (напр. «- scope_terms: türkei|tuerkei|turkei|turkey»): "
                            "ключ без жодного з цих слів не йде ні в кластери, ні в розподіл по сторінках")
    try:
        re.compile("|".join(terms))
    except re.error as e:
        raise ConfigMissing(f"scope_terms у {path}: некоректний вираз ({e})")
    d["scope_terms"] = terms
    d["location_code"] = int(d["location_code"])
    d["thr_ok"] = int(d.get("thr_ok", 5))
    d["thr_disputed"] = int(d.get("thr_disputed", 3))
    d["max_keywords"] = int(d.get("max_keywords", 100))
    d["preset"] = {"travel_de": "travel"}.get(d.get("preset", "travel"), d.get("preset", "travel"))
    d.setdefault("hotels_page", "")
    d.setdefault("lemma_regions", "")
    d.setdefault("hub_slugs", d["slug"])
    d.setdefault("hub_extra_regex", "")
    d["site"] = d["site"].rstrip("/")
    for r in d["business_rules"]:
        r["page"] = r.get("page", "").replace("{page_base}", d["page_base"])
    d["_site_source"] = sites[0][0] if sites else None
    d["_direction_source"] = path if direction else None
    d["_notes"] = notes
    for n in notes:
        print("УВАГА (налаштування):", n, file=sys.stderr)
    return Settings(d)


# ---------- journals: "### Журнал" inside "## <skill>" of the working folder's CLAUDE.md, never of a parent ----------
def _journal_bounds(lines, section):
    """(start of the journal block, end) inside "## <section>"; creates the section and the sub-heading when missing"""
    i = next((k for k, l in enumerate(lines) if re.match(r"^##\s*" + re.escape(section) + r"\b", l.strip(), re.I)), None)
    if i is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"## {section}", "", f"### {JOURNAL_HEADING}"]
        return len(lines), len(lines)
    end = next((k for k in range(i + 1, len(lines)) if re.match(r"^#{1,2}\s", lines[k])), len(lines))
    j = next((k for k in range(i + 1, end) if re.match(r"^#{3,6}\s*" + JOURNAL_HEADING, lines[k].strip(), re.I)), None)
    if j is None:
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = ["", f"### {JOURNAL_HEADING}"]
        return end + 2, end + 2
    stop = next((k for k in range(j + 1, end) if re.match(r"^#{1,6}\s", lines[k])), end)
    return j + 1, stop


def journal_read(workdir, section):
    path = os.path.join(workdir, "CLAUDE.md")
    if not os.path.exists(path):
        return []
    lines = open(path, encoding="utf-8").read().split("\n")
    if not any(re.match(r"^##\s*" + re.escape(section) + r"\b", l.strip(), re.I) for l in lines):
        return []
    a, b = _journal_bounds(lines, section)
    return [l for l in lines[a:b] if l.strip()]


def journal_add(workdir, section, key, line):
    """Add (or replace the entry that starts with "- <key>") a journal line; the file is created when missing."""
    path = os.path.join(workdir, "CLAUDE.md")
    lines = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else [f"# {os.path.basename(os.path.abspath(workdir))}"]
    a, b = _journal_bounds(lines, section)
    block = [l for l in lines[a:b] if l.strip() and not l.startswith(f"- {key}")] + [line]
    tail = lines[b:]
    lines[a:] = block + ([""] if tail and tail[0].strip() else []) + tail
    open(path, "w", encoding="utf-8").write("\n".join(lines).rstrip("\n") + "\n")
    return path


def config_help(err):
    return ("Не можу прочитати налаштування: " + str(err) + "\nДані сайту шукаю в CLAUDE.md поточної папки, потім у батьківських (до " + PROJECTS_ROOT
            + "); налаштування напрямку й журнал — лише в CLAUDE.md поточної папки. Шаблон (змініть значення під сайт):\n\n" + CONFIG_TEMPLATE)


def load_auth():
    """Basic auth header from ~/.config/claude-seo/dataforseo.env (never printed)."""
    vals = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    if not vals.get("DATAFORSEO_LOGIN") or not vals.get("DATAFORSEO_PASSWORD"):
        sys.exit("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not found in " + ENV_FILE)
    return "Basic " + base64.b64encode(f"{vals['DATAFORSEO_LOGIN']}:{vals['DATAFORSEO_PASSWORD']}".encode()).decode()


def api(auth, path, body, method="POST"):
    """Call https://api.dataforseo.com/v3/<path>; returns parsed JSON."""
    req = urllib.request.Request("https://api.dataforseo.com/v3/" + path, method=method,
                                 data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"Authorization": auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


class CostGuard:
    """Tracks real cost from the `cost` fields and stops when it exceeds the estimate by more than OVER_LIMIT."""

    def __init__(self, estimate, over=OVER_LIMIT):
        self.estimate, self.over, self.spent = estimate, over, 0.0

    def add(self, cost):
        self.spent += float(cost or 0)
        if self.estimate and self.spent > self.estimate * (1 + self.over):
            raise SystemExit(f"СТОП: витрати ${self.spent:.4f} перевищили оцінку ${self.estimate:.4f} більш ніж на {int(self.over * 100)}%")

    def __str__(self):
        return f"${self.spent:.4f} (оцінка ${self.estimate:.4f})"


def print_estimate(rows):
    """rows: [(label, count, unit_price)] -> prints the breakdown, returns total."""
    total = 0.0
    print("Розбивка вартості (оцінка зверху):")
    for label, n, price in rows:
        print(f"  {label:<60} {n:>4} × ${price:<6} = ${n * price:.3f}")
        total += n * price
    print(f"  {'РАЗОМ':<60} {'':>4}          ${total:.3f}")
    return total


# ---------- small text/url helpers ----------
SERP_COUNT_MAX = 1000        # a genuine google.de answer reports ~100-200 results; the degraded variant reports thousands
SERP_UNCONFIRMED = "SERP не підтверджено"


def serp_quality(resp):
    """Is a live/regular answer the genuine first page?  DataForSEO returns, for identical parameters, either the real TOP-10 or a
    degraded variant (deep pages with ?page=, forums, old articles; checked in a browser on 2026-10-08).  Signs of the degraded variant:
    no related_searches block, a ?page= URL among the organic results, se_results_count in the thousands."""
    res = resp["tasks"][0]["result"][0]
    organic = [it for it in (res.get("items") or []) if it["type"] == "organic"]
    reasons = []
    if "related_searches" not in (res.get("item_types") or []):
        reasons.append("немає блоку related_searches")
    if any(re.search(r"[?&]page=\d", it["url"]) for it in organic):
        reasons.append("?page= у ТОП-10")
    cnt = res.get("se_results_count") or 0
    if cnt >= SERP_COUNT_MAX:
        reasons.append(f"se_results_count {cnt}")
    return {"confirmed": not reasons, "reasons": reasons, "se_results_count": cnt, "task_id": resp["tasks"][0].get("id"), "datetime": res.get("datetime")}


def slug_file(kw):
    a = unicodedata.normalize("NFKD", kw).encode("ascii", "ignore").decode()
    a = re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-")[:50]
    return f"{a}-{hashlib.sha1(kw.encode('utf-8')).hexdigest()[:8]}"


def nu(u):
    """Normalised URL for overlaps: no scheme, www., query, fragment, trailing slash; lower-case host+path."""
    p = urlsplit(u)
    h = p.netloc.lower()
    h = h[4:] if h.startswith("www.") else h
    return h + p.path.lower().rstrip("/")


def reg_domain(host):
    parts = host.lower().split(":")[0].split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


# ---------- decisions file (manual decisions survive re-clustering) ----------
DECISIONS_FILE = "semantics-decisions.json"
DECISION_KEYS = {"business_rules": [], "keyword_overrides": {}, "contested_verdicts": {}, "manual_check": {}, "page_notes": {},
                 "known_positions": {}, "manual_filter": {}, "page_overrides": {}, "region_pages": {}, "serp_manual_check": {}}


def load_decisions(workdir="."):
    p = os.path.join(workdir, DECISIONS_FILE)
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    for k, v in DECISION_KEYS.items():
        d.setdefault(k, type(v)())
    return d


def save_decisions(workdir, d):
    json.dump(d, open(os.path.join(workdir, DECISIONS_FILE), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def apply_decisions_to_keywords(kw, dec):
    """In-place: manual_filter -> `filtered`, page_overrides -> keyword["page_override"]. Idempotent."""
    mf, po = dec.get("manual_filter", {}), dec.get("page_overrides", {})
    moved = [k for k in kw["keywords"] if k["keyword"] in mf]
    kw["keywords"] = [k for k in kw["keywords"] if k["keyword"] not in mf]
    have = {f["keyword"] for f in kw.setdefault("filtered", [])}
    for k in moved:
        if k["keyword"] not in have:
            kw["filtered"].append({"keyword": k["keyword"], "reason": mf[k["keyword"]]})
    for f in mf:
        if f not in have and not any(x["keyword"] == f for x in moved):
            pass
    for k in kw["keywords"]:
        if k["keyword"] in po:
            k["page_override"] = po[k["keyword"]]
    return kw


def load_rules(S, workdir="."):
    """Niche rules: <workdir>/semantics-rules.py if present, else presets/<preset>.py.  Returns (rules namespace, path)."""
    proj = os.path.join(workdir, "semantics-rules.py")
    path = proj if os.path.exists(proj) else os.path.join(SKILL_DIR, "presets", S.preset + ".py")
    spec = importlib.util.spec_from_file_location("sp_rules", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    S["_workdir"] = workdir
    try:
        return mod.make(S), path
    except ProfileMissing as e:
        sys.exit(str(e))


def norm_keyword(k, R=None):
    """Duplicate key: lower case, no hyphens/quotes, stop words and plural forms normalised, words sorted."""
    stop = getattr(R, "STOP", set())
    plural = getattr(R, "PLURAL", {})
    t = k.lower().replace("-", " ").replace("''", " ").replace("'", " ")
    t = re.sub(r"all[ -]?inclusive|all[ -]?inklusiv|alles inklusive", "ai", t)
    toks = [plural.get(x, x) for x in t.split() if x not in stop]
    return " ".join(sorted(toks))


# ---------------- market profiles (language/country dependent words, regexes, domains, brands, resorts) ----------------
PROFILES_DIR = os.path.join(SKILL_DIR, "scripts", "profiles")
PROFILE_OVERRIDE = "semantics-profile.json"


class ProfileMissing(Exception):
    pass


def profile_code(S):
    """Profile of the market: `profile:` from CLAUDE.md, else the TLD of se_domain (google.de -> de), else the language."""
    if S.get("profile"):
        return S["profile"]
    tld = S["se_domain"].rsplit(".", 1)[-1].lower()
    for code in (tld, S["language"].lower()):
        if os.path.exists(os.path.join(PROFILES_DIR, code + ".json")):
            return code
    return tld


def _merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def load_profile(S, workdir="."):
    """scripts/profiles/<code>.json merged with <workdir>/semantics-profile.json (project overrides)."""
    code = profile_code(S)
    path = os.path.join(PROFILES_DIR, code + ".json")
    if not os.path.exists(path):
        have = ", ".join(sorted(f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith(".json")))
        raise ProfileMissing(f"Профілю для ринку «{code}» (se_domain {S['se_domain']}, мова {S['language']}) немає в {PROFILES_DIR}. Є: {have}.\n"
                             f"Створіть {code}.json на основі de.json: переклад слів лем і класифікації посадкових (urlaub, pauschalreise, last-minute, all-inclusive, "
                             "frühbucher, rundreise, hotel), інформаційні домени, стоп-бренди, модифікатори (ціна, місяці), мовні списки токенів, "
                             "регіони/курорти країн призначення. Після створення повторіть команду. Можу підготувати чернетку профілю за ТОП-ами - скажіть.")
    prof = json.load(open(path, encoding="utf-8"))
    ov = os.path.join(workdir, PROFILE_OVERRIDE)
    if os.path.exists(ov):
        prof = _merge(prof, json.load(open(ov, encoding="utf-8")))
    return prof


if __name__ == "__main__":      # read-only: show where the settings of a folder come from (no API, nothing is written)
    import argparse
    ap = argparse.ArgumentParser(description="Показати налаштування папки: дані сайту, напрямок, журнали. Нічого не змінює.")
    ap.add_argument("--workdir", default=".")
    a = ap.parse_args()
    try:
        S = load_settings(a.workdir)
    except ConfigMissing as e:
        sys.exit(config_help(e))
    print("папка:            ", os.path.abspath(a.workdir))
    print("дані сайту з:     ", S["_site_source"] or "— (старий формат: усе в секції semantics-travel)")
    print("напрямок з:       ", S["_direction_source"] or "— (секції «## semantics-travel» у цій папці немає)")
    for k in ("site", "market", "language", "location_code", "se_domain", "profile", "country", "slug", "page_base", "hotels_page", "main_keyword"):
        if S.get(k) not in (None, ""):
            print(f"  {k}: {S[k]}")
    print("  scope_terms (межа збору):", " | ".join(S["scope_terms"]))
    print(f"  регіонів: {len(S['regions'])}, наявних сторінок: {len(S['existing_pages'])}, бізнес-правил: {len(S['business_rules'])}, посадкових під модифікатори: {len(S['modifier_pages'])}")
    for sec in ("semantics-travel", "tz-travel"):
        j = journal_read(a.workdir, sec)
        print(f"журнал {sec}: " + (f"{len(j)} записів" if j else "порожній"))
        for l in j:
            print("   ", l[:160])
