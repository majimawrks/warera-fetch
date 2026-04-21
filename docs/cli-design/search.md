# search

**Endpoint:** `search.searchAnything`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--query Q` | string | yes | — | Search term. No positional form — always flagged. |

## Resolution logic

Call `search.searchAnything` with `{"searchText": QUERY}`.

Note: `searchText` is the API param name (not `query`) — confirmed in smoke test.

## Output shape

Default: JSON with 6 fields (confirmed from live test — spec only documents 3):
`userIds`, `muIds`, `countryIds`, `regionIds`, `partyIds`, `hasData`

`--humanize`: ✅ New `humanize_search` function. Per-category count + ID list: "Users (3): id1, id2, id3 / MUs (1): id / ..." Match existing separator style.

Auto-name for bare `--output`: `search_<query>_<timestamp>.json`

## Examples

```sh
python fetch.py search --query warera
python fetch.py search --query Indonesia --humanize
python fetch.py search --query someuser --output
```

## Notes

- The response returns IDs only (not full objects). Use other aliases (`user --id`, `mu --id`, etc.) to fetch details.
- `--query` flag not `search Q` positional — enforces uniform flag contract.

## Backward-compat notes

New alias. Previously only used internally (user resolution in other handlers).
