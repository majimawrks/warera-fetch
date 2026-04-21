# region

**Endpoint:** `region.getById`
**Auth:** optional
**Status:** existing, enrich (add `--country`/`--country-id` resolution)
**Alias:** `region`

## Flags

| Flag | Type | Required | Default | Notes |
|---|---|---|---|---|
| `--id ID` | string | one of id/url/country | — | Raw regionId |
| `--url URL` | string | one of id/url/country | — | `app.warera.io` region URL |
| `--country NAME` | string | one of id/url/country | — | NEW: find capital region of country by name |
| `--country-id ID` | string | one of id/url/country | — | NEW: find capital region of country by raw ID |

Exactly one of `--id`, `--url`, `--country`, or `--country-id` is required.

## Resolution logic

1. If `--id`: use directly as `regionId`.
2. If `--url`: parse last path segment → `regionId`.
3. If `--country` or `--country-id` (**new**):
   - Resolve countryId from name if needed.
   - Fetch `country.getCountryById` to get the country's capital region ID.
   - Use that regionId to call `region.getById`.

## Output shape

Default: JSON region object.
See spec audit for actual fields: `stats, dates, _id, code, country, initialCountry, neighbors, isCapital, isLinkedToCapital, upgradesV2, name, mainCity, development, ...`

`--humanize`: ✅ New `humanize_region` function. Header block (═ × 55) + key fields from actual response: name, country, biome, isCapital, development, resistance, resistanceMax. Match `humanize_user_referrals` style.

Auto-name for bare `--output`: `region_<regionId-prefix>_<timestamp>.json`

## Examples

```sh
python fetch.py region --url https://app.warera.io/region/6813b703...
python fetch.py region --id 6813b703...
python fetch.py region --country Indonesia
python fetch.py region --country-id 6813b6d5...
```

## Backward-compat notes

`region --url` and `region --id` must keep working. `--country`/`--country-id` are new additions.
