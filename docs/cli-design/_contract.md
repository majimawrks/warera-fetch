# Uniform Flag Contract

All CLI aliases follow this flag set. Each alias documents which flags it uses.

---

## Identity resolution flags

### Primary entity flags (on the alias that owns the entity)

| Flag | Applies to | Behavior |
|---|---|---|
| `--id ID` | all single-entity aliases | Raw entity ID (MongoDB ObjectID). The alias context determines the ID type: `battle --id` = battleId, `mu --id` = muId, `country --id` = countryId, etc. |
| `--name NAME` | `country` | Primary entity name lookup. Resolved to ID via `country.getAllCountries` (case-insensitive substring). Currently only `country` supports name-based lookup. |
| `--url URL` | all single-entity aliases | Auto-parsed: extract entity ID from `app.warera.io` URL path. |
| `--uname USERNAME` | `user` | Username resolved to userId via `search.searchAnything`. Distinct from `--name` — it's a handle/login, not a display name. |

**Rule:** `--id`, `--name`, `--url`, `--uname` are *primary entity* flags. They appear only on the alias that owns the entity being fetched.

### Foreign / filter entity flags (cross-alias references)

| Flag | Applies to | Behavior |
|---|---|---|
| `--country NAME` | aliases with a country filter | Country name resolved to countryId via `country.getAllCountries`. |
| `--country-id ID` | aliases with a country filter | Raw countryId bypass — skips resolution. |
| `--user-id ID` | `referrals`, `sanctions` | Raw userId for user-scoped foreign reference. |
| `--battle-id ID` | `ranking --type battle` | Raw battleId foreign reference. |
| `--battle-url URL` | `ranking --type battle` | Auto-parsed battle URL. |

**Rule:** `--<type>-id` flags appear only on aliases where that entity type is a *filter or foreign key*, not the primary thing being fetched.

**Precedence when multiple identity flags given:** `--id` > `--url` > `--name` / `--uname`; `--<type>-id` > `--<type>` for foreign refs.

---

## Pagination flags

| Flag | Applies to | Notes |
|---|---|---|
| `--limit N` | paginated endpoints | Max results per call (integer). |
| `--cursor CURSOR` | paginated endpoints | Pagination cursor from previous response. |

---

## Filter flags

| Flag | Applies to | Notes |
|---|---|---|
| `--query Q` | `search` | Search term string. Maps to `searchText` API param. |
| `--language LANG [LANG …]` | article endpoints | One or more ISO 639-1 codes, e.g. `--language id en`. |
| `--article-type TYPE` | `articles` | Feed type: `daily weekly top my subscriptions last`. Default `last`. Maps to `type` API param. |
| `--event-type TYPE [TYPE …]` | `events` | Filter by one or more event type strings. Maps to `eventTypes[]` API param. |
| `--type TYPE` | `ranking` | Entity type for ranking: `user`, `country`, `mu`, or `battle` (dispatches to battleRanking). |
| `--item CODE` | `market`, `orders` | Item code e.g. `grain`, `oil`, `iron`. |
| `--data-type TYPE` | `ranking --type battle` | Metric to rank by: `damage` or `points`. Default `damage`. |
| `--side SIDE` | `ranking --type battle` | Which battle side: `attacker` or `defender`. |
| `--direction DIR` | `sanctions` | Pagination/sort direction. Likely `asc` or `desc` — verify from API. |
| `--active` | `battle --list` | Filter to active battles only (`isActive: true`). |

## Mode flags

| Flag | Applies to | Notes |
|---|---|---|
| `--list` | `battle` | Switch to list mode (`battle.getBattles`) instead of single-battle report. |
| `--lite` | `articles` (with `--id`/`--url`) | Use `article.getArticleLiteById` instead of full `getArticleById`. |

---

## Output flags

| Flag | Applies to | Notes |
|---|---|---|
| `--humanize` | singular endpoints only (see below) | Human-readable formatted text output instead of JSON. |
| `--output [FILE]` | all | Save result to file. Bare flag (no FILE) → auto-name (see naming rule). |
| `--format txt\|md\|json` | all | Override output format. Default `json`. |
| `--raw` | all | Compact JSON (no pretty-print). |

### `--humanize` scope

`--humanize` is accepted **only** on aliases that return a single entity or a short fixed-shape result. On paginated/list aliases it is rejected with: `"--humanize is not supported for list results; pipe to a file with --output or use --format md instead"`.

| Alias | `--humanize` | Humanizer function | Notes |
|---|---|---|---|
| `battle` (report) | ✅ | `humanize_battle_report` (existing) | |
| `articles` / `art` | ✅ | `humanize_articles` (existing) | list, but humanizer already exists — keep |
| `events` / `ev` | ✅ | `humanize_events` (existing) | list, but humanizer already exists — keep |
| `referrals` / `ref` | ✅ | `humanize_user_referrals` (existing) | list, but humanizer already exists — keep |
| `user` | ✅ | new — `humanize_user` | profile block matching existing style |
| `country` (single) | ✅ | new — `humanize_country` | key-value block |
| `region` | ✅ | new — `humanize_region` | key-value block |
| `mu` | ✅ | new — `humanize_mu` | key-value block |
| `party` | ✅ | new — `humanize_party` | key-value block |
| `market` | ✅ | new — `humanize_market` | compact price table |
| `orders` | ✅ | new — `humanize_orders` | two-section buy/sell table |
| `search` | ✅ | new — `humanize_search` | ID counts + lists per category |
| `battle --list` | ❌ | — | paginated |
| `country` (all) | ❌ | — | too many rows |
| `users` | ❌ | — | paginated |
| `sanctions` / `bans` | ❌ | — | paginated |
| `ranking` | ❌ | — | use JSON |
| `regions` | ❌ | — | large flat object |

**Style guide for new humanizer functions** (match existing style):
- Header block: `═` × 55 separator, key fields indented with 2 spaces
- Section headers: `KEY   value` (uppercase key, spaces to col 10)
- Dates: `%-d %B %Y` format (Windows: `%#d %B %Y`)
- Place new humanizer functions alongside the existing ones in `fetch.py` (after line ~1035)

**Auto-name rule for bare `--output`:**
`<alias>_<primary-identifier>_<YYYYMMDD-HHMMSS>.<ext>`
where `<primary-identifier>` is the first non-flag arg value (ID, username, query, or alias name if no args), and `<ext>` comes from `--format` (default `json`).

Examples:
- `python fetch.py battle --id 68f...e3 --output` → `battle_68fe3_20260420-143022.json`
- `python fetch.py search --query warera --output --format md` → `search_warera_20260420-143022.md`
- `python fetch.py market --output` → `market_20260420-143022.json`

---

## Debug / auth flags

| Flag | Applies to | Notes |
|---|---|---|
| `--debug` | all | Print every HTTP call with URL, status, and timing to stderr. |
| `--progress` | slow / paginated | tqdm progress bars on stderr. |
| `--token JWT` | all | JWT cookie override (sets `Cookie: jwt=<JWT>`). |
| `--api-key KEY` | all | X-API-Key header override. |

---

## URL parsing rules

`--url` accepts any `app.warera.io` URL. The parser extracts the last path segment as the entity ID and validates the hostname matches `app.warera.io`.

Examples:
- `https://app.warera.io/battle/68f...e3` → battleId `68f...e3`
- `https://app.warera.io/region/6813b703...` → regionId `6813b703...`
- `https://app.warera.io/country/6813b6d5...` → countryId `6813b6d5...`

---

## Auth behavior

Driven by the `auth` field in each endpoint's `specs/<endpoint>/spec.json`:

| Value | Behavior |
|---|---|
| `none` | No auth header sent. |
| `optional` | Auth used if available (JWT > API key). No error if absent. |
| `required` | Auth required. Hard fail with clear error if no token found. |

Token lookup order: `--token` flag → `--api-key` flag → `WARERA_TOKEN` env var → `WARERA_API_KEY` env var → browser cookie store → `.warera_token` file.

---

## No positional arguments

All aliases use `--flags` exclusively. No positional arguments on any alias.
The only exception is the existing `raw <endpoint>` command which predates this refactor and is kept as-is.
