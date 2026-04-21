# referrals / ref

**Endpoints:**
- Default: `referral.getUserReferralsPaginated`
- Fallback (API returns empty): `referral.getUserReferrals`

**Auth:** required
**Status:** existing, no change
**Aliases:** `referrals`, `ref`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--user-id ID` | string | one of user-id/uname | — | Raw userId whose referrals to fetch |
| `--uname USERNAME` | string | one of user-id/uname | — | Resolve via `search.searchAnything` → userId |
| `--limit N` | int | no | — | Max results |

## Resolution logic

1. If `--uname`: resolve to userId via `search.searchAnything`.
2. Call `referral.getUserReferralsPaginated` with `{userId, limit}` (no cursor — API has no cursor param).
3. If result is empty (API quirk), fall back to `referral.getUserReferrals` with `{userId}`.

## Auth behavior

Requires JWT. Emits hard error if no token found.

## Output shape

JSON `{items: [...], nextCursor: ...}`.

`--humanize`: ✅ Existing `humanize_user_referrals` function (profile header + numbered referral list with country + joined date).

## Examples

```sh
python fetch.py referrals --user-id 6813b703...
python fetch.py referrals --user-id 6813b703... --limit 20
python fetch.py ref --uname someuser
```

## Backward-compat notes

No changes to this alias.
