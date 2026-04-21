# fetch.py Refactor — Uniform CLI over All Endpoints

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor `fetch.py` so every known `api2.warera.io` tRPC endpoint has a first-class shortcode/alias with a uniform, consistent flag set.

**Architecture:** Three-phase approach —
1. **Freeze existing `specs/`** as personal API reference (dual JSON+MD format, endpoint-oriented) — unchanged.
2. **Design the CLI** in a new `docs/cli-design/` folder — alias-oriented, one file per alias, defines flag contract + which endpoint(s) each alias calls.
3. **Implement** the new parser and handlers against the design.

**Tech Stack:** Python 3.11+, argparse, asyncio, `warera_api.WaraApiClient`

---

## Endpoint Inventory (discovered from codebase)

23 tRPC endpoints identified across `fetch.py`, `market_tracker.py`, `ban_tracker.py`, `dashboard.py`, `debug.py`:

| Namespace | Method | Current CLI alias | Notes |
|---|---|---|---|
| article | getArticlesPaginated | `articles` / `art` | |
| article | getArticleById | (inline in `articles`) | no standalone alias |
| article | getArticleLiteById | (inline in `articles --lite`) | no standalone alias |
| battle | getById | (inline in `battle`) | no standalone alias |
| battle | getLiveBattleData | none | no alias at all |
| battle | getBattles | (inline in `battle --country`) | no standalone alias |
| battleRanking | getRanking | none | only via `raw` |
| country | getAllCountries | `country` (no args) | |
| country | getCountryById | `country --country` / `--url` | |
| event | getEventsPaginated | `events` / `ev` | |
| itemTrading | getPrices | none | only used by market_tracker |
| mu | getById | none | only via `raw mu.getById` |
| party | getById | none | only used by dashboard |
| ranking | getRanking | none | mentioned in `raw` examples only |
| referral | getUserReferrals | (fallback in `referrals`) | |
| referral | getUserReferralsPaginated | `referrals` / `ref` | |
| region | getById | `region --url` | no --country support |
| region | getRegionsObject | none | only used by dashboard |
| sanction | getPaginated | none | only used by ban_tracker |
| search | searchAnything | none | only internal use |
| tradingOrder | getTopOrders | none | only used by market_tracker |
| user | getUserLite | `user` | |
| user | getUsersByCountry | none | only used by ban_tracker |

---

## Folder layout

```
specs/                      # EXISTING — personal API reference, do not modify in this refactor
  <namespace>.<method>/
    spec.json               # machine-readable endpoint doc
    spec.md                 # human-readable endpoint doc

docs/cli-design/            # NEW — alias-oriented CLI design (source of truth for Task 3)
  _contract.md              # shared flag contract + naming rules
  _command-map.md           # alias → endpoint(s) index
  <alias>.md                # one file per CLI alias (new + existing)
```

Rationale: `specs/` documents **endpoints** (what the API offers). `docs/cli-design/` documents **aliases** (what the CLI exposes). An alias may call multiple endpoints (e.g. `battle` calls `battle.getById` then enriches with `battle.getLiveBattleData`); one endpoint may be reachable through multiple aliases. The two layers should not be collapsed.

---

## Task 1: Freeze `specs/` and validate coverage

`specs/` already contains 23 endpoint folders. No writes — only verification.

**Steps:**

1. Confirm all 23 endpoints from the inventory have a `specs/<name>/spec.json` and `spec.md`.
2. For each `spec.json`, smoke-test the endpoint live (api_key auth) and diff the real response's top-level keys against `output_sample_fields`. Note discrepancies but do not fix here — flag for a separate docs pass.
3. Output: a single `docs/cli-design/_spec-audit.md` listing any coverage gaps or schema drift found. If clean, the file just says "All 23 specs verified on YYYY-MM-DD".

---

## Task 2: Design the CLI in `docs/cli-design/`

### 2a. Write `_contract.md` — the uniform flag contract

| Flag | Applies to | Notes |
|---|---|---|
| `--id ID` | all entity lookups | Raw entity ID, alternative to `--url` |
| `--url URL` | all entity lookups | Auto-parsed to inject correct ID param |
| `--country NAME` | country-scoped endpoints | Resolved to ID via `country.getAllCountries` |
| `--country-id ID` | country-scoped endpoints | Raw ID bypass |
| `--uname USERNAME` | user-scoped endpoints | Resolved via `search.searchAnything` |
| `--user-id ID` | user-scoped endpoints | Raw ID bypass |
| `--query Q` | `search` alias | Search term (flagged, not positional, to stay uniform) |
| `--limit N` | paginated endpoints | Max results |
| `--cursor CURSOR` | paginated endpoints | Pagination cursor |
| `--language LANG+` | article endpoints | ISO codes |
| `--humanize` | all | Human-readable text output |
| `--output [FILE]` | all | Save to file; bare flag → auto-name |
| `--format txt\|md\|json` | all | Override extension-based format detection |
| `--raw` | all | Compact JSON (no pretty-print) |
| `--debug` | all | Print every HTTP call with timing |
| `--progress` | slow/paginated | tqdm progress bars |
| `--token JWT` | all | JWT cookie override |
| `--api-key KEY` | all | X-API-Key override |

**Auto-name rule for bare `--output`:** `<alias>_<primary-id-or-query>_<YYYYMMDD-HHMMSS>.<ext>` where ext comes from `--format` (default `json`). Examples: `battle_68f..e3_20260420-143022.json`, `search_warera_20260420-143155.md`.

**Positional vs flag rule:** **All** aliases use flags only, no positionals. (`search --query Q` not `search Q`.)

### 2b. Write `_command-map.md` — the alias table

| Alias | Endpoint(s) called | Status | Notes |
|---|---|---|---|
| `articles` / `art` | `article.getArticlesPaginated` (+ `getArticleById` / `getArticleLiteById` when `--id`/`--url`) | existing, enrich | |
| `events` / `ev` | `event.getEventsPaginated` | existing | |
| `battle` | `battle.getById` + `battle.getLiveBattleData` | existing, enrich | single battle report |
| `battle --list` | `battle.getBattles` | existing flag, keep | country-scoped list (no separate `battles` alias — avoids singular/plural typo) |
| `country` | `country.getAllCountries` OR `country.getCountryById` | existing | behavior depends on flags |
| `region` | `region.getById` | existing, enrich | add `--country` resolution |
| `regions` | `region.getRegionsObject` | **new** | no params |
| `user` | `user.getUserLite` | existing | |
| `users` | `user.getUsersByCountry` | **new** | |
| `referrals` / `ref` | `referral.getUserReferralsPaginated` (+ `getUserReferrals` fallback) | existing | |
| `market` | `itemTrading.getPrices` | **new** | `--item CODE` optional; `prices` not added as synonym |
| `orders` | `tradingOrder.getTopOrders` | **new** | `--item CODE` |
| `mu` | `mu.getById` | **new** | `--url`, `--id` |
| `party` | `party.getById` | **new** | `--url`, `--id` |
| `search` | `search.searchAnything` | **new** | `--query Q` |
| `ranking` | `ranking.getRanking` OR `battleRanking.getRanking` | **new** | `--type user\|country\|mu\|battle`; when `--type battle`, require `--battle-id`/`--battle-url` |
| `sanctions` / `bans` | `sanction.getPaginated` | **new** | `--user-id`, `--uname`, `--country`, `--limit` |
| `raw` | any endpoint by dotted path | existing | escape hatch — stays forever |

**Alias decisions resolved vs the original plan:**
- **No `market`/`prices` synonym pair** — pick `market` only.
- **No `battle` vs `battles` split** — keep one `battle` alias, use `--list` flag for the list mode. Typo-safe.
- **`search` uses `--query`, not positional** — enforces uniform contract.
- **`ranking` covers both `ranking.getRanking` and `battleRanking.getRanking`** via `--type`, with `--type battle` requiring a battle ref. Documented explicitly in `ranking.md`.

### 2c. Per-alias design file

One `docs/cli-design/<alias>.md` per alias. Template:

```markdown
# <alias>

**Endpoint(s):** `namespace.method` (+ optional follow-ups)
**Auth:** required | optional | none

## Flags
| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|

## Resolution logic
(How `--url` / `--uname` / `--country` get translated to IDs, order of precedence, what happens when multiple are given.)

## Output shape
(Default JSON, `--humanize` format, file naming if `--output` used.)

## Examples
```sh
```

## Backward-compat notes
(Any existing behavior preserved for this alias.)
```

**Steps:**
1. Write `_contract.md` and `_command-map.md` first.
2. Write one alias file per row of the command map (~18 files). Start with existing aliases to lock in backward-compat, then new ones.
3. Self-review: grep that every flag used in any alias file is defined in `_contract.md`.

---

## Task 3: Implement new CLI

Only after Task 2 is complete and reviewed.

**Files:**
- Modify: `fetch.py` — add new subcommands, enrich existing ones with missing flags
- Modify: `warera_api.py` — add convenience wrappers for newly-aliased endpoints
- Update: `docs/fetch.md` — regenerate from new parser

**Implementation order (simple → complex, so the flag plumbing stabilizes before the hard cases):**

1. **No-param endpoints:** `regions`, `market` (no `--item`)
2. **Single-ID lookups:** `mu`, `party`
3. **Country-scoped lookups:** `users`, enrich `region --country`
4. **Paginated with filters:** `orders`, `sanctions`
5. **Search:** `search --query`
6. **Composite:** `ranking` (dispatches to two endpoints), `battle --list` enrichment
7. **Regression sweep:** run the smoke-test script (see below) against every existing alias.

**Per-alias workflow:**
1. Read `docs/cli-design/<alias>.md`.
2. Add subparser entry in `build_parser()`.
3. Add handler branch in `main()`.
4. Add a line to `tests/smoke_cli.sh` (or `.py`) — a one-shot invocation of the alias with minimal args that asserts exit code 0 and non-empty JSON.
5. Run smoke-test script end-to-end — new alias passes AND all prior aliases still pass.
6. Commit: `feat(cli): add <alias> for <endpoint>`.

**Regression guard:** `tests/smoke_cli.sh` must be green before every commit. New aliases append; existing rows never removed.

---

## Notes

- Do **not** break existing aliases (`events`, `articles`, `battle`, `referrals`, `user`, `country`, `region`, `raw`) — full backward-compat. Existing-alias rows in the smoke-test script are the contract.
- `raw` escape hatch stays forever as the catch-all for undocumented endpoints. Update `raw --help` examples to prefer first-class aliases where available, but keep all raw invocations working.
- Auth column in specs drives which auth warning to emit (required → hard fail, optional → api_key works, none → no auth needed).
- `specs/` is the personal API reference and is **not** rewritten by this refactor. Any endpoint schema corrections found during Task 1 validation are logged to `_spec-audit.md` and addressed in a separate follow-up, not mixed into the CLI refactor commits.
