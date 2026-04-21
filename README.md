# warera-fetch

A command-line tool for fetching data from the [WarEra](https://app.warera.io) game API. Every known tRPC endpoint has a first-class alias with a uniform flag set, JSON output, and optional human-readable formatting.

## Requirements

- Python 3.11+
- Dependencies auto-installed on first run via `_require()`: `httpx`, `tqdm`

## Authentication

Most read-only endpoints work without auth. Some (rankings, referrals) require an API key.

Create `.warera_token` in the project directory:

```json
{
  "api_key": "wae_your_key_here"
}
```

Get your API key: **Warera → Settings → API Tokens**

---

## Commands

```
python fetch.py <command> [flags]
```

| Command | Description | Key flags |
|---|---|---|
| `events` / `ev` | In-game event feed | `--country`, `--event-types`, `--limit` |
| `articles` / `art` | News articles | `--article-type`, `--uname`, `--language`, `--limit` |
| `battle` | Battle dossier (rounds, rankings, alliances) | `--id`, `--url`, `--country` |
| `battle --list` | List battles | `--active`, `--country`, `--limit` |
| `country` | Country detail or list all | `--id`, `--name`, `--url` |
| `region` | Region detail | `--id`, `--url`, `--country` |
| `regions` | All regions as a flat object | — |
| `user` | Player profile | `--id`, `--url`, `--uname` |
| `users` | Users in a country | `--country`, `--country-id`, `--limit` |
| `referrals` / `ref` | User referral list | `--url`, `--uname`, `--limit` |
| `market` | Market prices | `--item CODE` (optional filter) |
| `orders` | Top buy/sell orders | `--item CODE` (required) |
| `mu` | Military unit profile | `--id`, `--url` |
| `party` | Political party profile | `--id`, `--url` |
| `sanctions` / `bans` | Sanctions list | `--user-id`, `--uname`, `--limit` |
| `search` | Search users/MUs/countries/regions/parties | `--query Q` |
| `ranking` | Global rankings | `--type METRIC`, `--limit` |
| `ranking --type battle` | Battle rankings | `--battle-id`, `--data-type`, `--side` |
| `raw` | Call any tRPC endpoint directly | `<endpoint> --params '{...}'` |

---

## Common usage examples

```bash
# Events
python fetch.py events --limit 10
python fetch.py events --country Indonesia --event-types battleOpened battleEnded

# Articles
python fetch.py articles --article-type top --limit 5 --humanize
python fetch.py articles --uname majima

# Battle
python fetch.py battle --country Indonesia --humanize
python fetch.py battle --url https://app.warera.io/battle/<id>
python fetch.py battle --list --active --limit 10

# Country & region
python fetch.py country --name Indonesia
python fetch.py country
python fetch.py region --country Indonesia    # fetches capital region
python fetch.py region --url https://app.warera.io/region/<id>

# User & users
python fetch.py user --uname majima
python fetch.py users --country Indonesia --limit 50

# Market
python fetch.py market
python fetch.py market --item grain --humanize
python fetch.py orders --item grain --humanize

# Search
python fetch.py search --query warera

# Rankings (requires API key)
python fetch.py ranking --type userDamages --limit 20
python fetch.py ranking --type countryWealth
python fetch.py ranking --type battle --battle-id <id> --data-type points --side attacker

# MU & party
python fetch.py mu --id <muId>
python fetch.py party --url https://app.warera.io/party/<id>

# Sanctions
python fetch.py sanctions --limit 10
python fetch.py sanctions --uname someuser

# Raw escape hatch
python fetch.py raw country.getAllCountries
python fetch.py raw event.getEventsPaginated --params '{"countryId":"<id>","limit":5}'
```

---

## Output flags

All commands support these output flags:

| Flag | Effect |
|---|---|
| `--humanize` | Formatted text output instead of JSON (singular / short-result commands only) |
| `--output [FILE]` | Save to file. Bare flag → auto-named: `<alias>_<id>_<timestamp>.json` |
| `--format txt\|md\|json` | Override format (default `json`) |
| `--raw` | Compact JSON (no pretty-print) |

---

## Ranking metrics

`ranking --type` accepts any of these 25 metric strings:

**Country:** `weeklyCountryDamages` `weeklyCountryDamagesPerCitizen` `countryRegionDiff` `countryDevelopment` `countryActivePopulation` `countryDamages` `countryWealth` `countryProductionBonus` `countryBounty`

**User:** `weeklyUserDamages` `userDamages` `userWealth` `userLevel` `userReferrals` `userSubscribers` `userTerrain` `userPremiumMonths` `userPremiumGifts` `userCasesOpened` `userGemsPurchased` `userBounty`

**MU:** `muWeeklyDamages` `muDamages` `muTerrain` `muWealth` `muBounty`

Use `--type battle` with `--battle-id` / `--battle-url` for in-battle rankings.

---

## URL shorthand

Any `app.warera.io` URL can be passed as the first argument and the right subcommand is auto-detected:

```bash
python fetch.py https://app.warera.io/battle/<id> --humanize
python fetch.py https://app.warera.io/region/<id>
python fetch.py https://app.warera.io/mu/<id>
```

---

## Project structure

```
fetch.py          — main CLI (~2000 lines, single file, self-installing deps)
warera_api.py     — WaraApiClient (httpx async, 429 retry, semaphore)
tests/
  smoke_cli.sh    — one-row-per-alias smoke test (bash)
  test_*.py       — pytest unit tests
CHANGELOG.md      — change history
```

---

## Testing

```bash
# Smoke test (bash required — git-bash on Windows)
bash tests/smoke_cli.sh

# Unit tests
python -m pytest tests/

# With API key for auth-required rows
WARERA_API_KEY=wae_... bash tests/smoke_cli.sh
```

---

## License

MIT — see [LICENSE](LICENSE).

> This is an unofficial third-party tool. Not affiliated with the WarEra game or its developers.
