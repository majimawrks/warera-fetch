# mu

**Endpoint:** `mu.getById`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | one of id/url | — | Raw muId (MongoDB ObjectID) |
| `--url URL` | string | one of id/url | — | `app.warera.io` MU URL; last path segment extracted as muId |

Exactly one of `--id` or `--url` is required.

## Resolution logic

1. If `--id`: use directly as `muId`.
2. If `--url`: parse last path segment from URL → `muId`.

Call: `mu.getById` with `{"muId": <resolved_id>}`.

## Output shape

Default: JSON object representing the MU.

`--humanize`: ✅ New `humanize_mu` function. Header block (═ × 55) + key fields: name, country, memberCount, president, founded date. Match `humanize_user_referrals` style.

Auto-name for bare `--output`: `mu_<muId-prefix>_<timestamp>.json`

## Examples

```sh
python fetch.py mu --id 6813b703...
python fetch.py mu --url https://app.warera.io/mu/6813b703...
python fetch.py mu --id 6813b703... --humanize
```

## Backward-compat notes

New alias. Previously only accessible via `raw mu.getById --params '{"muId":"..."}'`.
