# regions

**Endpoint:** `region.getRegionsObject`
**Auth:** optional
**Status:** new

## Flags

None. This endpoint takes no input parameters.

Global flags (`--debug`, `--token`, `--api-key`, `--raw`, `--humanize`, `--output`, `--format`) apply as always.

## Resolution logic

No resolution needed. Single call with empty params `{}`.

## Output shape

Default: JSON object keyed by regionId (MongoDB ObjectID strings), values are region summary objects.

`--humanize`: ❌ Not supported (large flat object). Use `--output` to save.

Auto-name for bare `--output`: `regions_<YYYYMMDD-HHMMSS>.json`

## Examples

```sh
python fetch.py regions
python fetch.py regions --output
python fetch.py regions --humanize
```

## Backward-compat notes

New alias — no existing behavior.
