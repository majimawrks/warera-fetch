# orders

**Endpoint:** `tradingOrder.getTopOrders`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--item CODE` | string | yes | — | Item code e.g. `grain`, `oil`, `iron`, `steel` |

## Resolution logic

Call `tradingOrder.getTopOrders` with `{"itemCode": CODE}`.

## Output shape

Default: JSON `{buyOrders: [...], sellOrders: [...]}`.
> Note: spec documents fields as `buy`/`sell` — live test confirms the actual names are `buyOrders`/`sellOrders`. Use the live names.

`--humanize`: ✅ New `humanize_orders` function. Two sections (BUY ORDERS / SELL ORDERS), each a table: rank | price | qty | country. Match existing separator style.

Auto-name for bare `--output`: `orders_<itemCode>_<timestamp>.json`

## Examples

```sh
python fetch.py orders --item grain
python fetch.py orders --item oil --humanize
python fetch.py orders --item iron --output
```

## Backward-compat notes

New alias. Previously only used internally by `market_tracker.py`.
