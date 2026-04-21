# country

**Endpoints:**
- No args: `country.getAllCountries`
- With `--id`/`--name`/`--url`: `country.getCountryById`

**Auth:** none
**Status:** existing, no change
**Alias:** `country`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | no | — | Raw countryId; calls `getCountryById` directly |
| `--name NAME` | string | no | — | Country name (case-insensitive substring match); resolved to countryId via `getAllCountries` |
| `--url URL` | string | no | — | `app.warera.io` country URL; last path segment extracted as countryId |

When none of the above given: calls `getAllCountries` and returns the full list.

## Resolution logic

1. If `--id`: call `getCountryById` with that ID directly.
2. If `--url`: extract countryId from URL, call `getCountryById`.
3. If `--name`: call `getAllCountries`, find first country whose `name` contains the given string (case-insensitive), call `getCountryById` with `_id`.
4. If nothing: call `getAllCountries`.

## Output shape

All countries: JSON array of country objects.
Single country: JSON object. Actual fields (from live test): `taxes, unrest, _id, name, code, money, orgs, allies, warsWith, scheme, mapAccent, __v, strategicResources, rankings, updatedAt, development, specializedItem, enemy, rulingParty`.

`--humanize` (single country): ✅ New `humanize_country` function. Header block (═ × 55) + key fields: name, code, money, taxes, unrest, allies, warsWith, rulingParty. Match existing style.
`--humanize` (all countries / no args): ❌ Not supported (too many rows).

## Examples

```sh
python fetch.py country
python fetch.py country --name Indonesia
python fetch.py country --id 6813b6d5...
python fetch.py country --url https://app.warera.io/country/6813b6d5...
```

## Backward-compat notes

`--country NAME` and `--country-id ID` are removed from this alias — replaced by `--name` and `--id` respectively.
`--country` and `--country-id` remain on **other** aliases where country is a foreign filter (e.g. `users --country Indonesia`).
