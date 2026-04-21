# Changelog

All notable changes to this project are documented here.
Entries are grouped by the refactor task that produced them.

---

## [Unreleased] — Task 3 implementation (2026-04-21)

### Added — new CLI aliases

| Alias | Endpoint | Notes |
|---|---|---|
| `regions` | `region.getRegionsObject` | All regions as a flat keyed object |
| `market` | `itemTrading.getPrices` | All prices; `--item CODE` filters client-side |
| `orders` | `tradingOrder.getTopOrders` | Top buy/sell orders; `--item CODE` required |
| `mu` | `mu.getById` | Military unit profile; `--id` / `--url` |
| `party` | `party.getById` | Political party profile; `--id` / `--url` |
| `users` | `user.getUsersByCountry` | Paginated user list; `--country` / `--country-id` |
| `sanctions` / `bans` | `sanction.getPaginated` | Paginated sanctions; `--user-id` / `--uname` / `--direction` |
| `search` | `search.searchAnything` | Entity search; `--query Q` (required) |
| `ranking` | `ranking.getRanking` / `battleRanking.getRanking` | Metric rankings; see type enum |

### Changed — existing alias enrichments

- **`battle`**: added `--id` (direct dossier lookup), `--list` (list mode via `battle.getBattles`), `--active` (list filter), `--limit`
- **`country`**: replaced `--country` / `--country-id` with `--id` (direct, dest=`country_id`) and `--name` (name lookup, dest=`country_name`); backward-compat URL parsing preserved
- **`user`**: added `--id` (dest=`user_id`) as primary identity flag; `--url` and `--uname` still supported
- **`region`**: added `--id` (dest=`region_id`); added `--country` / `--country-id` to fetch the country's capital region via `region.getRegionsObject`

### Added — humanizer functions

`humanize_user`, `humanize_country`, `humanize_region`, `humanize_mu`, `humanize_party`, `humanize_market`, `humanize_orders`, `humanize_search`, `_fmt_date` (shared helper)

### Added — infrastructure

- `tests/smoke_cli.sh` — one row per alias; `run_auth` helper skips rows when no `WARERA_API_KEY` is set
- `VALID_RANKING_TYPES` constant in `fetch.py` — 25 metric strings from live API

### Fixed

- `URL_PARAM_MAP` extended with `"party": "partyId"` for `--url` support on `party`
- `_url_autodispatch` now maps `mu` → `mu` and `party` → `party` subcommands
- `auto_output_path` extended with prefixes for all new aliases

### Spec drift discovered (2026-04-21)

- `ranking.getRanking`: `type` enum changed from `user/country/mu` to 25 specific metric strings (e.g. `userDamages`, `countryWealth`). CLI updated accordingly.
- `itemTrading.getPrices`: `itemCode` param is silently ignored; API always returns all prices. Client-side filter applied in `market --item`.

---

## [Unreleased] — Task 2: CLI design (2026-04-20)

### Added — `docs/cli-design/`

New alias-oriented design layer created. Files are the source of truth for Task 3 implementation.

| File | Contents |
|---|---|
| `_contract.md` | Uniform flag contract: primary vs foreign entity flags, pagination, output, auth, URL parsing rules |
| `_command-map.md` | Full alias↔endpoint table, per-alias param mapping, implementation order |
| `_spec-audit.md` | Live smoke-test results for all 23 endpoints; schema drift notes |
| `articles.md` | Existing alias; confirmed `--article-type` naming; `--uname` via search |
| `battle.md` | Existing alias; enrichment flags documented |
| `country.md` | Rewritten: `--id` / `--name` / `--url`; no `--country-id` on owning alias |
| `events.md` | Updated: `--country`, `--event-type` documented |
| `market.md` | New alias |
| `mu.md` | New alias |
| `orders.md` | New alias; `buyOrders`/`sellOrders` output field names confirmed |
| `party.md` | New alias; `URL_PARAM_MAP` addition noted |
| `ranking.md` | New alias |
| `referrals.md` | Existing; no `--cursor` (API has none) |
| `region.md` | Enriched: `--id`, `--country`/`--country-id` |
| `regions.md` | New alias |
| `sanctions.md` | New alias; `targetUserId` API param; no `--country` |
| `search.md` | New alias; `searchText` param confirmed from live test |
| `user.md` | Rewritten: `--id` primary flag; removed `--user-id` |
| `users.md` | New alias |

---

## [Unreleased] — Task 1: Spec audit (2026-04-20)

### Added

- `docs/cli-design/_spec-audit.md` — live endpoint verification for all 23 specs
- `CLAUDE.md` — execution guidelines for AI-assisted development

### Key findings

- `search.searchAnything` param is `searchText`, not `query`
- `article.getArticlesPaginated` requires `type` param (not optional in practice)
- `tradingOrder.getTopOrders` output fields are `buyOrders`/`sellOrders` (spec says `buy`/`sell`)
- `country.getCountryById` and `region.getById` output fields differ significantly from spec docs
- `ranking.getRanking` required auth (and later found to have a changed `type` enum)

---

## Auth subsystem redesign (2026-04-20 → 2026-04-21)

### Changed

- JWT hidden behind explicit `--jwt` flag (was auto-loaded from env/browser/file)
- `_confirm_jwt_use()` prompt added — warns of ban risk and requires `y` to proceed
- `resolve_token()` rewritten: JWT only from `--jwt`; API key from `--api-key` → `WARERA_API_KEY` env → `.warera_token` file
- `WARERA_TOKEN` env var now prints an info message instead of silently loading JWT
- Browser cookie auto-read removed
- `.warera_token` file now only reads `api_key` field (legacy JWT field ignored)
- `_AUTH_EPILOG` updated to show API key as the recommended auth method
