# ranking

**Endpoints:**
- `ranking.getRanking` — for `--type user|country|mu`
- `battleRanking.getRanking` — for `--type battle`

**Auth:** optional (possibly required in practice — see spec audit)
**Status:** new

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--type TYPE` | string | yes | — | `user`, `country`, `mu`, or `battle` |
| `--limit N` | int | no | — | Max results (for `user`/`country`/`mu` types) |
| `--battle-id ID` | string | required if `--type battle` | — | Raw battleId |
| `--battle-url URL` | string | required if `--type battle` | — | `app.warera.io` battle URL; last path segment extracted as battleId |
| `--data-type TYPE` | string | no (battle only) | `damage` | `damage` or `points` (battleRanking only) |
| `--side SIDE` | string | no (battle only) | — | `attacker` or `defender` (battleRanking only) |

## Resolution logic

**If `--type` is `user`, `country`, or `mu`:**
- Call `ranking.getRanking` with `{"type": TYPE, "limit": N}`.
- Note: spec audit found this endpoint may require auth — emit a warning if no token found.

**If `--type` is `battle`:**
- Require `--battle-id` or `--battle-url` (error if neither given).
- Resolve battle ID from URL if needed.
- Call `battleRanking.getRanking` with `{"battleId": ID, "dataType": DATA_TYPE, "type": "user", "side": SIDE}`.

## Output shape

Default: JSON. Response shape differs by type:
- `ranking.getRanking` → `{rankings: [...]}` (inferred from codebase usage)
- `battleRanking.getRanking` → `{rankings: [...]}` (inferred)

`--humanize`: ❌ Not supported (use JSON output).

Auto-name for bare `--output`:
- `ranking_user_<timestamp>.json`
- `ranking_battle_<battleId-prefix>_<timestamp>.json`

## Examples

```sh
python fetch.py ranking --type user
python fetch.py ranking --type country --limit 20
python fetch.py ranking --type battle --battle-id 68f...e3
python fetch.py ranking --type battle --battle-url https://app.warera.io/battle/68f...e3 --data-type points --side attacker
```

## Backward-compat notes

New alias. Previously `battleRanking.getRanking` accessible only via `raw`. `ranking.getRanking` was mentioned in raw examples only.
