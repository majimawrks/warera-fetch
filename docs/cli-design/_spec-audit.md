# Spec Audit — 2026-04-20

All 23 endpoint spec folders verified present (`specs/<endpoint>/spec.json` + `spec.md`).
Live smoke-test run unauthenticated against `api2.warera.io`.

---

## Summary

| Status | Count |
|---|---|
| Confirmed OK | 12 |
| Reachable (404 = ID not found, expected) | 5 |
| Confirmed OK but schema drift in spec | 2 |
| Could not verify without auth/real IDs | 4 |
| Skipped (auth=required, no token) | 2 |

---

## Confirmed OK

| Endpoint | Params used | Actual top-level keys | Notes |
|---|---|---|---|
| `battle.getBattles` | `{limit:1}` | `items, nextCursor` | matches spec |
| `country.getAllCountries` | `{}` | array of country objects | matches spec |
| `event.getEventsPaginated` | `{limit:1}` | `items, nextCursor` | matches spec |
| `itemTrading.getPrices` | `{}` | flat object keyed by item code (cookedFish, heavyAmmo, steel, bread, grain, …) | spec uses `<itemCode>` placeholder — correct |
| `region.getRegionsObject` | `{}` | object keyed by MongoDB IDs | spec uses `<regionId>` placeholder — correct |
| `sanction.getPaginated` | `{limit:1}` | `items, nextCursor` | matches spec |
| `article.getArticlesPaginated` | `{type:"last", limit:1}` | `items, nextCursor` | matches spec; see drift note below |
| `search.searchAnything` | `{searchText:"warera"}` | `userIds, muIds, countryIds, regionIds, partyIds, hasData` | spec param name `searchText` is correct |
| `tradingOrder.getTopOrders` | `{itemCode:"grain"}` | `buyOrders, sellOrders` | matches spec |
| `country.getCountryById` | real countryId from getAllCountries | `taxes, unrest, _id, name, code, money, orgs, allies, warsWith, scheme, mapAccent, __v, strategicResources, rankings, updatedAt, development, specializedItem, enemy, rulingParty` | see drift note below |
| `user.getUsersByCountry` | real countryId | `items, nextCursor` | matches spec |
| `region.getById` | real regionId from getRegionsObject | `stats, dates, _id, code, country, initialCountry, neighbors, isCapital, isLinkedToCapital, upgradesV2, name, mainCity, development, baseDevelopment, countryCode, position, biome, climate, __v, resistance, activeUpgradeLevels, resistanceMax, lastResistanceContributionAt, lastRevoltEndedAt, lastBattleEndedAt` | see drift note below |

---

## Reachable — 404 with Test IDs (Expected)

These endpoints returned HTTP 404 because fake MongoDB IDs were used. The endpoint routing and auth layer are working correctly.

| Endpoint | Test ID used | Notes |
|---|---|---|
| `article.getArticleById` | `67eb5cba4e7afff0b9093e72` (fake) | endpoint reachable |
| `article.getArticleLiteById` | `67eb5cba4e7afff0b9093e72` (fake) | endpoint reachable |
| `battle.getById` | `67eb5cba4e7afff0b9093e71` (fake) | endpoint reachable |
| `battle.getLiveBattleData` | `67eb5cba4e7afff0b9093e71` (fake) | endpoint reachable |
| `user.getUserLite` | `67eb5cba4e7afff0b9093e70` (fake) | endpoint reachable |

---

## Schema Drift Found

These do not block the CLI refactor, but the specs should be updated in a separate docs pass.

### `article.getArticlesPaginated` — `type` param appears required in practice

- **Spec says:** `type` is `required: false`, default `"last"`
- **Observed:** calling with `{limit:1}` (no `type`) returns HTTP 400. Adding `{type:"last", limit:1}` returns 200 OK.
- **Impact on CLI:** the `articles` handler should always include `type` in the call, defaulting to `"last"`.

### `country.getCountryById` — output fields significantly differ from spec

- **Spec documents:** `_id, name, productionBonuses, government, economy, regions`
- **Actual response:** `taxes, unrest, _id, name, code, money, orgs, allies, warsWith, scheme, mapAccent, __v, strategicResources, rankings, updatedAt, development, specializedItem, enemy, rulingParty`
- **Impact on CLI:** `--humanize` output for `country` must use actual field names, not spec.

### `region.getById` — output fields significantly differ from spec

- **Spec documents:** `_id, name, country, productionBonuses, deposits, occupationStatus, developmentLevel, taxRate`
- **Actual response:** `stats, dates, _id, code, country, initialCountry, neighbors, isCapital, isLinkedToCapital, upgradesV2, name, mainCity, development, baseDevelopment, countryCode, position, biome, climate, __v, resistance, activeUpgradeLevels, resistanceMax, lastResistanceContributionAt, lastRevoltEndedAt, lastBattleEndedAt`
- **Impact on CLI:** same as above — use actual fields in `--humanize`.

---

## Could Not Verify

| Endpoint | Reason | Recommendation |
|---|---|---|
| `mu.getById` | 500 with test ID `"1"` — needs real muId (MongoDB ObjectID) | Verify manually with a real mu URL from the game |
| `party.getById` | 500 with test ID `"1"` — needs real partyId | Verify manually with a real party URL |
| `battleRanking.getRanking` | 400 with correct `battleId` param — may require a currently-active or recently-active battle ID, or JWT | Verify with a real recent battle ID or with auth |
| `ranking.getRanking` | Consistently 400 for all `type` values (`user`, `country`, `mu`) without auth — may require JWT in practice despite `auth: optional` in spec | Verify with auth; update spec `auth` field to `required` if confirmed |

---

## Skipped (auth=required)

| Endpoint | Notes |
|---|---|
| `referral.getUserReferrals` | Requires JWT |
| `referral.getUserReferralsPaginated` | Requires JWT |

---

## Action Items (separate docs pass, not this refactor)

1. Update `specs/article.getArticlesPaginated/spec.json` — set `type.required: true` (or document that omitting it causes 400)
2. Update `specs/country.getCountryById/spec.json` + `spec.md` — replace output fields with actual fields listed above
3. Update `specs/region.getById/spec.json` + `spec.md` — replace output fields with actual fields listed above
4. ~~Verify `ranking.getRanking` with auth~~ — **Done 2026-04-21**: endpoint verified; `type` enum has changed (see drift note below).
5. ~~Verify `mu.getById`, `party.getById` with real IDs~~ — **Done 2026-04-21**: both confirmed reachable; `battleRanking.getRanking` still unverified (needs real battle ID).

---

## Additional Drift — 2026-04-21

### `ranking.getRanking` — `type` enum completely replaced

- **Spec documents:** `type` ∈ `{ "user", "country", "mu" }`
- **Actual API (live, 2026-04-21):** `type` must be one of 25 specific metric strings:
  - Country: `weeklyCountryDamages`, `weeklyCountryDamagesPerCitizen`, `countryRegionDiff`, `countryDevelopment`, `countryActivePopulation`, `countryDamages`, `countryWealth`, `countryProductionBonus`, `countryBounty`
  - User: `weeklyUserDamages`, `userDamages`, `userWealth`, `userLevel`, `userReferrals`, `userSubscribers`, `userTerrain`, `userPremiumMonths`, `userPremiumGifts`, `userCasesOpened`, `userGemsPurchased`, `userBounty`
  - MU: `muWeeklyDamages`, `muDamages`, `muTerrain`, `muWealth`, `muBounty`
- **Impact:** CLI `ranking --type` was updated to accept these values. Old `user/country/mu` shorthand removed. `VALID_RANKING_TYPES` constant added to `fetch.py`.
- **Auth:** API key (`X-API-Key`) is sufficient — no JWT required.

### `itemTrading.getPrices` — `itemCode` param is ignored

- **Spec implies:** pass `itemCode` to filter by item.
- **Actual API:** always returns all prices regardless of `itemCode` param.
- **Impact:** `market --item CODE` now filters client-side in `fetch.py`.
