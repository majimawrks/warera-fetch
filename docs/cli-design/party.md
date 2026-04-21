# party

**Endpoint:** `party.getById`
**Auth:** optional
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | one of id/url | — | Raw partyId (MongoDB ObjectID) |
| `--url URL` | string | one of id/url | — | `app.warera.io` party URL; last path segment extracted as partyId |

Exactly one of `--id` or `--url` is required.

## Resolution logic

1. If `--id`: use directly as `partyId`.
2. If `--url`: parse last path segment from URL → `partyId`.

Call: `party.getById` with `{"partyId": <resolved_id>}`.

## Output shape

Default: JSON object representing the party.

`--humanize`: ✅ New `humanize_party` function. Header block (═ × 55) + key fields: name, country, memberCount, president, founded date. Match `humanize_user_referrals` style.

Auto-name for bare `--output`: `party_<partyId-prefix>_<timestamp>.json`

## Examples

```sh
python fetch.py party --id 6813b703...
python fetch.py party --url https://app.warera.io/party/6813b703...
python fetch.py party --id 6813b703... --humanize
```

## Backward-compat notes

New alias. Previously only accessible via `raw party.getById --params '{"partyId":"..."}'`.
