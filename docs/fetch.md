# fetch.py

Swiss-army CLI for the Warera API. Provides domain-specific subcommands (events, articles, battles, referrals, user profiles, regions, countries) plus a `raw` escape hatch for any tRPC endpoint. Outputs JSON by default; `--humanize` switches to readable text; `--output` saves to file.

---

## Role in the project

Standalone CLI tool — not imported by other scripts. Self-contained with its own auth loading, URL parsing, output formatting, and humanization logic.

---

## Commands

```
python fetch.py [--db PATH] <command> [options]
```

| Command | Endpoint(s) used | Description |
|---|---|---|
| `events` / `ev` | `event.getEventsPaginated` | In-game news feed |
| `articles` / `art` | `article.getArticlesPaginated`, `article.getArticleById` | Articles by country, user, or ID |
| `battle` / `bat` | `battle.getReport` (composite) | Full battle dossier |
| `referrals` / `ref` | `referral.getUserReferrals*` | User profile + referral list |
| `user` | `user.getUserLite` | Player profile |
| `country` | `country.getCountryById` / `getAllCountries` | Country info |
| `region` | `region.getById` | Region info |
| `raw` | any endpoint | Power-user escape hatch |

Short aliases (`ev`, `art`, `bat`, `ref`) work identically to their full forms.

**URL auto-dispatch:** if the first argument looks like a `https://app.warera.io/…` URL, the subcommand is inferred automatically:
```
python fetch.py https://app.warera.io/battle/<id> --humanize
# → same as: python fetch.py battle --url https://app.warera.io/battle/<id> --humanize
```

---

## Shared flags (most commands)

| Flag | Description |
|---|---|
| `--country NAME` | Filter by country name (case-insensitive, partial match OK) |
| `--country-id ID` | Filter by raw country ID |
| `--url URL` | Warera URL — entity ID is auto-extracted |
| `--uname USERNAME` | Look up user by username (search + profile fetch) |
| `--limit N` | Number of results (default varies; `None` → API decides) |
| `--humanize` | Human-readable text output instead of JSON |
| `--output [FILE]` | Save to file; bare `--output` auto-names as `output/<entity>-<id>.<fmt>` |
| `--format {txt,md,json}` | Force output format (overrides file extension) |
| `--raw` | Raw compact JSON (no pretty-print) |
| `--progress` | Show tqdm progress bars |
| `--debug` | Print every API call + timing to stderr |
| `--token TOKEN` | JWT cookie value |
| `--api-key KEY` | X-API-Key value |

---

## Command details

### `events`

```
python fetch.py events --country Indonesia --limit 20 --humanize
python fetch.py events --country Indonesia --event-types warDeclared battleOpened
```

`--event-types` filters by one or more of the 18 valid event types: `warDeclared`, `peace_agreement`, `battleOpened`, `battleEnded`, `newPresident`, `regionTransfer`, `peaceMade`, `countryMoneyTransfer`, `depositDiscovered`, `depositDepleted`, `systemRevolt`, `bankruptcy`, `allianceFormed`, `allianceBroken`, `regionLiberated`, `strategicResourcesReshuffled`, `resistanceIncreased`, `resistanceDecreased`.

Humanized output groups events by date with icons (⚔️, 🕊️, 🔍, etc.).

### `articles`

Three routing modes depending on what filter is given:

| Mode | Trigger | Behaviour |
|---|---|---|
| Single article | `--url https://…/article/<id>` or `--id <id>` | Calls `getArticleById` directly |
| By author | `--uname USERNAME` | Client-side filter over global feed (warns if page cap reached) |
| By country | `--country` or `--country-id` | Client-side filter by author's country |
| Global feed | no filter | Calls `getArticlesPaginated` directly |

```
python fetch.py articles --country Indonesia --limit 10 --humanize --output articles.md
python fetch.py articles --uname majima --humanize
python fetch.py articles --url https://app.warera.io/article/<id> --humanize
```

Article-type flag: `--article-type {daily,weekly,top,my,subscriptions,last}` (default: `last`)
Language filter: `--language id en`

### `battle`

Fetches a composite battle dossier: metadata, per-round scores, top fighters by damage and ground points, alliance orders, MU orders, and bounty pools.

```
python fetch.py battle --country Indonesia --humanize
python fetch.py battle --url https://app.warera.io/battle/<id> --humanize --output report.md
```

When given `--country`, picks the first active battle for that country. If multiple active battles exist, logs the others.

### `referrals`

Requires JWT authentication.

```
python fetch.py referrals --uname majima --humanize
python fetch.py referrals --url https://app.warera.io/user/<id> --humanize
```

Returns user profile + resolved referral list (each referral fetched via `getUserLite`). Falls back from `getUserReferralsPaginated` to `getUserReferrals` on error.

### `user` / `country` / `region`

Simple profile lookups:
```
python fetch.py user --uname majima
python fetch.py country --country Indonesia
python fetch.py region --url https://app.warera.io/region/<id>
```

### `raw`

Direct endpoint call — use for any endpoint not covered by other commands:
```
python fetch.py raw itemTrading.getPrices --params '{"countryId":"abc"}'
python fetch.py raw search.searchAnything --params '{"searchText":"majima"}'
```

---

## Key functions

### Fetching

```python
# Battle composite fetch — concurrent rounds + rankings + ID resolution
report = await fetch_battle_report(client, battle_id, show_progress=False)

# Articles filtered by country (client-side, max 10 pages × 100 items)
articles, user_map = await fetch_articles_by_country(client, country_id, limit, article_type, languages)

# Articles by author (client-side filter, warns if page cap reached)
articles, user_map = await fetch_articles_by_user(client, user_id, limit, article_type, languages)

# Referrals + profile + country names
profile, referrals, country_map = await fetch_user_referrals(client, user_id, limit)
```

### Humanization

```python
text = humanize_events(events, country_map, region_map, user_map)
text = humanize_battle_report(report)
text = humanize_user_referrals(user_id, profile, referrals, country_map)
text = humanize_articles(articles, user_map)
```

### URL parsing

```python
entity_type, entity_id = parse_warera_url("https://app.warera.io/battle/abc123")
# → ("battle", "abc123")
```

Supported entity types: `battle`, `article`, `user`, `country`, `region`, `mu`, `referral`.

`URL_PARAM_MAP` maps entity type to the API param name (e.g. `battle` → `battleId`).

---

## Auth resolution: `resolve_token(args)`

Priority order:

1. `--token` / `--api-key` CLI flags
2. `WARERA_TOKEN` / `WARERA_API_KEY` env vars
3. `.warera_token` file — JSON `{"jwt": "...", "api_key": "..."}` or legacy plain-text JWT
4. Browser cookie store — Chrome / Firefox / Edge via `browser-cookie3` package

If the stored JWT is expired and a fresh one is found in the browser, `.warera_token` is updated automatically (preserving `api_key`).

Token file location: **same directory as `fetch.py`** (resolved via `Path(__file__).parent`), not the shell's current directory.

---

## Output routing

`resolve_format(args, out_path)` determines format:
1. `--format` flag wins
2. File extension of `--output` path (`.txt`, `.md`, `.json`)
3. `"txt"` if `--humanize` is set
4. `"json"` otherwise

`auto_output_path(args, entity_id)` generates `output/<prefix>-<ident>.<fmt>` when `--output` is given without a filename. Format is resolved first so the extension matches.

---

## Shared helper: `_fatal(msg)`

Prints to stderr and calls `sys.exit(1)`. Used by resolver helpers (`resolve_country_name`, `resolve_user_by_name`) to centralise exit handling.

---

## Dependencies

```
pip:    httpx, tqdm, browser-cookie3
stdlib: argparse, asyncio, base64, json, os, re, time, datetime, pathlib, sys, subprocess
local:  warera_api.WaraApiClient
```

---

## How to extend

### Add a new subcommand

1. Add a subparser in `build_parser()` — use `parents=[_shared_filter_group]` if it takes country/url/uname
2. Write `async def` handler in `main()` under the new `if cmd == "newcmd":` block
3. Add to examples in epilog

### Add a new event type

1. Add the type string to `VALID_EVENT_TYPES`
2. Add an icon to `EVENT_ICONS`
3. Add a formatting branch in `format_event()`

### Support a new output format

Add a branch in `resolve_format()` and a matching save path in the output block that calls the humanizer for that format.
