# battle

**Endpoints:**
- Default: `battle.getById` + `battle.getLiveBattleData` (full battle dossier)
- `--list`: `battle.getBattles` (paginated list)

**Auth:** optional
**Status:** existing, enrich (--list flag already exists; document and lock it)
**Alias:** `battle` only

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | one of id/url/country (unless --list) | — | Raw battleId |
| `--url URL` | string | one of id/url/country (unless --list) | — | `app.warera.io` battle URL; last path segment extracted |
| `--country NAME` | string | one of id/url/country | — | Find active battle for this country (dossier mode); or filter list (--list mode) |
| `--country-id ID` | string | same | — | Raw countryId bypass |
| `--list` | flag | no | false | Fetch list of battles (`battle.getBattles`) instead of single report |
| `--active` | flag | no | false | With `--list`: filter to active battles only (`isActive: true`) |
| `--limit N` | int | no | — | Max results (with `--list` only; no cursor — API has no nextCursor) |

## Resolution logic

**Single battle report** (no `--list`):
1. Require `--id` or `--url`. Error if neither given.
2. Extract battleId from URL if `--url`.
3. Call `battle.getById` and `battle.getLiveBattleData` concurrently with `{"battleId": ID}`.
4. Merge results into full dossier.

**Battle list** (`--list`):
1. If `--country`: resolve to countryId via `country.getAllCountries`.
2. If `--country-id`: use directly.
3. Build params: `countryId` (if given), `isActive: true` (if `--active`), `limit`.
4. Call `battle.getBattles`. Response has `items` only — no `nextCursor`, no cursor pagination.

> Note: existing code hardcodes `isActive: True` when `--country` is used in dossier mode. `--active` is only meaningful in `--list` mode.

## Output shape

Single report: JSON dossier with meta, rounds, rankings.
List: JSON `{items: [...], nextCursor: ...}`.

`--humanize` (report): ✅ Existing `humanize_battle_report` function (header, score, round-by-round breakdown, top fighters).
`--humanize` (with `--list`): ❌ Not supported (paginated).

## Examples

```sh
python fetch.py battle --id 68f...e3
python fetch.py battle --url https://app.warera.io/battle/68f...e3
python fetch.py battle --list
python fetch.py battle --list --country Indonesia
python fetch.py battle --list --limit 10
```

## Backward-compat notes

`battle --id` and `battle --url` must keep working as before.
`battle --country` (without `--list`) was the old way to list battles — verify this is being preserved by the existing handler or migrate it to `--list --country`.
