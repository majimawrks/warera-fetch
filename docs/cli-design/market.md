# market

**Endpoint:** `itemTrading.getPrices`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--item CODE` | string | no | — | Filter to a single item code e.g. `grain`, `oil`, `iron`. If omitted, all prices returned. |

## Resolution logic

- If `--item` provided: pass `{"itemCode": CODE}` to endpoint.
- If `--item` omitted: pass `{}` — API returns flat object with all item codes as keys.

Note: `itemTrading.getPrices` without params returns all prices. With `itemCode` it may return a filtered subset — verify behavior.

## Output shape

Default: JSON. Full response is a flat object keyed by item code, values are price objects.

`--humanize`: ✅ New `humanize_market` function. Compact two-column price table: item code | price. Match existing separator style (═ × 55).

Auto-name for bare `--output`:
- With `--item grain`: `market_grain_<timestamp>.json`
- Without `--item`: `market_<timestamp>.json`

## Examples

```sh
python fetch.py market
python fetch.py market --item grain
python fetch.py market --item oil --humanize
python fetch.py market --output
```

## Backward-compat notes

New alias — no existing behavior. No `prices` synonym (single canonical name).
