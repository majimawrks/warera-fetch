# users

**Endpoint:** `user.getUsersByCountry`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--country NAME` | string | one of country/country-id | — | Country name resolved to ID via `country.getAllCountries` (case-insensitive) |
| `--country-id ID` | string | one of country/country-id | — | Raw countryId bypass |
| `--limit N` | int | no | — | Max results |
| `--cursor CURSOR` | string | no | — | Pagination cursor |

Exactly one of `--country` or `--country-id` is required.

## Resolution logic

1. If `--country-id`: use directly.
2. If `--country`: call `country.getAllCountries`, find first country whose `name` contains the given string (case-insensitive), extract `_id`.
3. Call `user.getUsersByCountry` with `{"countryId": <resolved_id>, ...pagination}`.

## Output shape

Default: JSON `{items: [...], nextCursor: ...}`.

`--humanize`: ❌ Not supported (paginated list).

Auto-name for bare `--output`: `users_<country-name-or-id>_<timestamp>.json`

## Examples

```sh
python fetch.py users --country Indonesia
python fetch.py users --country-id 6813b6d5...
python fetch.py users --country Indonesia --limit 50
```

## Backward-compat notes

New alias. Previously only used internally by `ban_tracker.py`.
