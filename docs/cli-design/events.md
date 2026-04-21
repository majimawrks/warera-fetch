# events / ev

**Endpoint:** `event.getEventsPaginated`
**Auth:** optional
**Status:** existing, no change
**Aliases:** `events`, `ev`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--country NAME` | string | no | — | Filter events by country (resolved to `countryId`) |
| `--country-id ID` | string | no | — | Raw `countryId` bypass |
| `--event-type TYPE+` | string[] | no | — | One or more event type strings (nargs="+"). Maps to `eventTypes[]` API param. See valid values below. |
| `--limit N` | int | no | — | Max events |
| `--cursor CURSOR` | string | no | — | Pagination cursor |

**Valid `--event-type` values:** `warDeclared`, `peaceMade`, `battleOpened`, `battleEnded`, `newPresident`, `regionTransfer`, `countryMoneyTransfer`, `depositDiscovered`, `depositDepleted`, `systemRevolt`, `bankruptcy`, `allianceFormed`, `allianceBroken`, `regionLiberated`, `strategicResourcesReshuffled`, `resistanceIncreased`, `resistanceDecreased`, `revolutionStarted`, `revolutionEnded`, `financedRevolt`

## Resolution logic

1. If `--country`: resolve name to `countryId` via `country.getAllCountries`.
2. If `--country-id`: use directly.
3. Call `event.getEventsPaginated` with `{countryId, eventTypes, limit, cursor}` as available.

## Output shape

JSON `{items: [...], nextCursor: ...}`.

`--humanize`: ✅ Existing `humanize_events` function (date-grouped, time + description per event).

## Examples

```sh
python fetch.py events
python fetch.py ev --limit 20
python fetch.py events --cursor <cursor>
```

## Backward-compat notes

No changes to this alias.
