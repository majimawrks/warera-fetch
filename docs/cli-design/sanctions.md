# sanctions / bans

**Endpoint:** `sanction.getPaginated`
**Auth:** optional
**Status:** new
**Aliases:** `sanctions`, `bans`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--user-id ID` | string | no | — | Filter by raw `targetUserId` (API param name is `targetUserId`) |
| `--uname USERNAME` | string | no | — | Resolve username → `targetUserId` via `search.searchAnything` |
| `--direction DIR` | string | no | — | Pagination/sort direction. Likely `asc` or `desc` — verify from live API. Maps to `direction` param. |
| `--limit N` | int | no | — | Max results |

All filters are optional; omitting all returns recent sanctions.

> **Note:** `--country`/`--country-id` are NOT supported — `sanction.getPaginated` has no `countryId` input param.

## Resolution logic

1. If `--uname` given (and no `--user-id`): resolve via `search.searchAnything` → first `userIds` result → use as `targetUserId`.
2. Build params: `{"targetUserId": ..., "direction": ..., "limit": ...}`, omitting absent fields.
3. Call `sanction.getPaginated`.

## Output shape

Default: JSON `{items: [...], nextCursor: ...}`.

`--humanize`: ❌ Not supported (paginated list).

Auto-name for bare `--output`:
- With `--uname foo`: `sanctions_foo_<timestamp>.json`
- No filter: `sanctions_<timestamp>.json`

## Examples

```sh
python fetch.py sanctions
python fetch.py bans --uname someuser
python fetch.py sanctions --user-id 6813b703... --limit 20
python fetch.py sanctions --direction desc --limit 10
```

## Backward-compat notes

New alias. Previously only used internally by `ban_tracker.py`.
