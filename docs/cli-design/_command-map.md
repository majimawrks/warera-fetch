# Command Map

Alias → endpoint(s) index. Source of truth for Task 3 implementation order.

Derived from: live endpoint responses, `specs/` JSON, and existing `fetch.py` behaviour.
Cross-checked: every flag maps to a real API param or a client-side resolution step.

---

## Full alias table

| Alias | Endpoint(s) called | Status | Key flags |
|---|---|---|---|
| `articles` / `art` | `article.getArticlesPaginated` (default); `article.getArticleById` / `article.getArticleLiteById` when `--id`/`--url` | existing, enrich | `--id`, `--url`, `--article-type`, `--uname`, `--limit`, `--cursor`, `--language`, `--lite` |
| `events` / `ev` | `event.getEventsPaginated` | existing, enrich | `--country`, `--country-id`, `--event-type`, `--limit`, `--cursor` |
| `battle` | `battle.getById` + `battle.getLiveBattleData` (dossier) | existing, enrich | `--id`, `--url`, `--country`, `--country-id` |
| `battle --list` | `battle.getBattles` | existing flag, enrich | `--country`, `--country-id`, `--active`, `--limit` ¹ |
| `country` | `country.getAllCountries` OR `country.getCountryById` | existing, enrich | `--id`, `--name`, `--url` |
| `region` | `region.getById` | existing, enrich | `--url`, `--id`, `--country`, `--country-id` |
| `regions` | `region.getRegionsObject` | **new** | (no params) |
| `user` | `user.getUserLite` | existing, enrich | `--id`, `--url`, `--uname` |
| `users` | `user.getUsersByCountry` | **new** | `--country`, `--country-id`, `--limit`, `--cursor` |
| `referrals` / `ref` | `referral.getUserReferralsPaginated` (+ `getUserReferrals` fallback) | existing, no change | `--user-id`, `--uname`, `--limit` ² |
| `market` | `itemTrading.getPrices` | **new** | `--item CODE` (optional — omit for all prices) |
| `orders` | `tradingOrder.getTopOrders` | **new** | `--item CODE` (required) |
| `mu` | `mu.getById` | **new** | `--url`, `--id` |
| `party` | `party.getById` | **new** | `--url`, `--id` |
| `search` | `search.searchAnything` | **new** | `--query Q` (required) |
| `ranking` | `ranking.getRanking` OR `battleRanking.getRanking` | **new** | `--type user\|country\|mu\|battle`; `--type battle` requires `--battle-id`/`--battle-url`, `--data-type`, `--side` |
| `sanctions` / `bans` | `sanction.getPaginated` | **new** | `--user-id`, `--uname`, `--direction`, `--limit` ³ |
| `raw` | any tRPC endpoint by dotted path | existing, no change | `<endpoint> --params '{...}'` |

---

## Param ↔ API field mapping (per alias)

### `articles` / `art`

| CLI flag | API param | Endpoint | Notes |
|---|---|---|---|
| `--id` / `--url` | `articleId` | `getArticleById` / `getArticleLiteById` | URL last-segment |
| `--article-type` | `type` | `getArticlesPaginated` | enum: `daily weekly top my subscriptions last`; default `last` |
| `--uname` | (client-side) | → resolve userId via `search.searchAnything`, then filter feed | API has no author filter |
| `--language` | `languages` | `getArticlesPaginated` | array of ISO codes |
| `--limit` | `limit` | `getArticlesPaginated` | |
| `--cursor` | `cursor` | `getArticlesPaginated` | |
| `--lite` | — | switches endpoint to `getArticleLiteById` | only applies with `--id`/`--url` |
| `--country` | (client-side) | → resolve to countryId, then filter authors from that country | API has no countryId param |

### `events` / `ev`

| CLI flag | API param | Notes |
|---|---|---|
| `--country` | `countryId` | resolved via `country.getAllCountries` |
| `--country-id` | `countryId` | raw bypass |
| `--event-type` | `eventTypes[]` | nargs="+"; valid values: `warDeclared peaceMade battleOpened battleEnded newPresident regionTransfer countryMoneyTransfer depositDiscovered depositDepleted systemRevolt bankruptcy allianceFormed allianceBroken regionLiberated strategicResourcesReshuffled resistanceIncreased resistanceDecreased revolutionStarted revolutionEnded financedRevolt` |
| `--limit` | `limit` | |
| `--cursor` | `cursor` | |

### `battle` (dossier mode)

| CLI flag | API param | Endpoint | Notes |
|---|---|---|---|
| `--id` | `battleId` | `getById` + `getLiveBattleData` | direct lookup |
| `--url` | `battleId` | same | URL last-segment extraction |
| `--country` | `countryId` | `getBattles` (to find active battle) | resolved via `getAllCountries`; picks first active battle in that country |
| `--country-id` | `countryId` | same | raw bypass |

### `battle --list`

| CLI flag | API param | Notes |
|---|---|---|
| `--country` | `countryId` | optional filter |
| `--country-id` | `countryId` | raw bypass |
| `--active` | `isActive: true` | default when flag present; omit flag to get all battles |
| `--limit` | `limit` | |
| ~~`--cursor`~~ | — | `getBattles` returns `items` only, no `nextCursor` |

### `country`

| CLI flag | API param | Endpoint | Notes |
|---|---|---|---|
| `--id` | `countryId` | `getCountryById` | direct lookup |
| `--name` | resolved → `countryId` | `getAllCountries` then `getCountryById` | case-insensitive substring match |
| `--url` | `countryId` | `getCountryById` | URL last-segment |
| (none) | — | `getAllCountries` | returns full array |

### `region`

| CLI flag | API param | Endpoint | Notes |
|---|---|---|---|
| `--id` | `regionId` | `getById` | |
| `--url` | `regionId` | `getById` | URL last-segment |
| `--country` | resolved → capital `regionId` | `getCountryById` then `getById` | fetch country → get capital region |
| `--country-id` | same | same | raw bypass |

### `user`

| CLI flag | API param | Notes |
|---|---|---|
| `--id` | `userId` | direct |
| `--url` | `userId` | URL last-segment |
| `--uname` | resolved → `userId` | via `search.searchAnything` → first `userIds` result |

> `--user-id` does NOT exist on the `user` alias. It is a foreign-reference flag on `referrals` and `sanctions` only.

### `users`

| CLI flag | API param | Notes |
|---|---|---|
| `--country` | resolved → `countryId` | |
| `--country-id` | `countryId` | raw bypass |
| `--limit` | `limit` | |
| `--cursor` | `cursor` | |

### `referrals` / `ref`

| CLI flag | API param | Notes |
|---|---|---|
| `--user-id` | `userId` | |
| `--uname` | resolved → `userId` | via `search.searchAnything` |
| `--limit` | `limit` | |
| ~~`--cursor`~~ | — | `getUserReferralsPaginated` spec has no cursor param |

### `market`

| CLI flag | API param | Notes |
|---|---|---|
| `--item` | `itemCode` (optional) | omit for full price map |

### `orders`

| CLI flag | API param | Notes |
|---|---|---|
| `--item` | `itemCode` | **required** |

Response output fields (from live test): `buyOrders`, `sellOrders` — note: spec incorrectly documents these as `buy`/`sell`.

### `mu`

| CLI flag | API param | Notes |
|---|---|---|
| `--id` | `muId` | |
| `--url` | `muId` | URL last-segment (entity type `mu`) |

### `party`

| CLI flag | API param | Notes |
|---|---|---|
| `--id` | `partyId` | |
| `--url` | `partyId` | URL last-segment (entity type `party`) — verify `party` is a valid URL_PARAM_MAP key |

> **Note:** `party` is NOT in the current `URL_PARAM_MAP`. Add `"party": "partyId"` to that dict in Task 3.

### `search`

| CLI flag | API param | Notes |
|---|---|---|
| `--query Q` | `searchText` | param name is `searchText`, not `query` (confirmed in smoke test) |

Response output (from live test — 6 fields, spec only documents 3):
`userIds`, `muIds`, `countryIds`, `regionIds`, `partyIds`, `hasData`

### `ranking`

| CLI flag | API param | Endpoint | Notes |
|---|---|---|---|
| `--type user\|country\|mu` | `type` | `ranking.getRanking` | required |
| `--type battle` | — | `battleRanking.getRanking` | dispatches to different endpoint |
| `--limit` | `limit` | `ranking.getRanking` | not applicable for battle type |
| `--battle-id` | `battleId` | `battleRanking.getRanking` | required when `--type battle` |
| `--battle-url` | `battleId` | same | URL last-segment |
| `--data-type` | `dataType` | `battleRanking.getRanking` | `damage` (default) or `points` |
| `--side` | `side` | `battleRanking.getRanking` | `attacker` or `defender` |

### `sanctions` / `bans`

| CLI flag | API param | Notes |
|---|---|---|
| `--user-id` | `targetUserId` | note: API param name is `targetUserId`, not `userId` |
| `--uname` | resolved → `targetUserId` | via `search.searchAnything` → first `userIds` result |
| `--direction` | `direction` | pagination/sort direction; values TBD from API (likely `asc`/`desc`) |
| `--limit` | `limit` | |
| ~~`--country`~~ | — | NOT a valid API param for `sanction.getPaginated` |

---

## Footnotes

¹ `battle.getBattles` response has `items` but no `nextCursor` — cursor-based pagination not available.

² `referral.getUserReferralsPaginated` spec has no `cursor` param — no cursor flag.

³ `sanction.getPaginated` has no `countryId` param — `--country` filter is removed.

---

## URL_PARAM_MAP additions needed (Task 3)

The existing `URL_PARAM_MAP` in `fetch.py` is missing:
```python
"party": "partyId",   # add for --url support on party alias
```

---

## Implementation order (Task 3)

**Group A — No-param / trivial:**
1. `regions` — no params, one call
2. `market` — optional `--item`

**Group B — Single-ID lookups:**
3. `mu` — `--id`/`--url`
4. `party` — `--id`/`--url` (+ add `party` to URL_PARAM_MAP)

**Group C — Country-scoped:**
5. `users` — `--country`/`--country-id` + pagination
6. Enrich `region` — add `--country`/`--country-id`

**Group D — Paginated with filters:**
7. `orders` — required `--item`
8. `sanctions` / `bans` — `--user-id`/`--uname`, `--direction`

**Group E — Search:**
9. `search` — `--query`

**Group F — Complex / multi-endpoint:**
10. `ranking` — dispatches to two endpoints based on `--type`
11. Enrich `events` — add `--country`/`--country-id` and `--event-type`
12. Enrich `battle --list` — expose `--active` flag, confirm no cursor

**Group G — Existing alias corrections:**
13. Enrich `articles` — confirm `--article-type` naming, lock in `--uname` behaviour

---

## Backward-compat regression list

```sh
python fetch.py articles
python fetch.py art --article-type top --limit 5
python fetch.py articles --language id en
python fetch.py articles --country Indonesia --limit 10
python fetch.py events --limit 10
python fetch.py ev
python fetch.py events --event-types battleOpened battleEnded
python fetch.py battle --country Indonesia
python fetch.py battle --url https://app.warera.io/battle/<id>
python fetch.py country
python fetch.py country --name Indonesia
python fetch.py country --id <id>
python fetch.py region --url https://app.warera.io/region/<id>
python fetch.py user --uname <username>
python fetch.py user --id <id>
python fetch.py referrals --user-id <id>
python fetch.py ref
python fetch.py raw article.getArticlesPaginated --params '{"type":"top"}'
```
