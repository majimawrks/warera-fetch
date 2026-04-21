# user

**Endpoint:** `user.getUserLite`
**Auth:** optional
**Status:** existing, no change
**Alias:** `user`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | one of id/url/uname | — | Raw userId |
| `--url URL` | string | one of id/url/uname | — | `app.warera.io` user URL; last path segment extracted as userId |
| `--uname USERNAME` | string | one of id/url/uname | — | Resolve via `search.searchAnything` → first `userIds` result |

Exactly one required. `--user-id` does not exist on this alias — use `--id`. (`--user-id` is a foreign-reference flag that appears on other aliases like `referrals` and `sanctions`.)

## Resolution logic

1. `--id`: use directly as `userId`.
2. `--url`: extract userId from URL.
3. `--uname`: call `search.searchAnything` with `{searchText: username}` → first `userIds` result.

Call `user.getUserLite` with `{"userId": <id>}`.

## Output shape

JSON user lite object. Actual fields: `_id, username, login, country, level, xp, experience, createdAt, infos`.

`--humanize`: ✅ New `humanize_user` function. Header block (═ × 55) + key fields: username, country (resolved name), level, XP, joined date. Match `humanize_user_referrals` profile-block style.

Auto-name for bare `--output`: `user_<id-prefix>_<timestamp>.json`

## Examples

```sh
python fetch.py user --uname someuser
python fetch.py user --id 6813b703...
python fetch.py user --url https://app.warera.io/user/6813b703...
```

## Backward-compat notes

`--user-id` is removed from this alias. Only `--id` is accepted for direct ID input.
