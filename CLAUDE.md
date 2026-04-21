# warera-fetch — Execution Guidelines

You are executing the refactor described in [docs/plans/2026-04-01-fetch-refactor.md](docs/plans/2026-04-01-fetch-refactor.md). Read the plan first. Use the `superpowers:executing-plans` skill and work **one task at a time**.

## Project at a glance

- `fetch.py` — ~1700-line single-file CLI, argparse subcommands, async handlers.
- `warera_api.py` — `WaraApiClient` wrapping `api2.warera.io/trpc` (httpx async, 429 retry, semaphore).
- `specs/` — 23 endpoint reference docs (JSON + MD per endpoint). **Do not modify in this refactor.**
- `docs/cli-design/` — **you will create this.** Alias-oriented design, source of truth for Task 3.
- `tests/` — pytest (`test_warera_api.py`, `test_battle_report.py`).

## Environment

- Windows + git-bash. Use Unix syntax (`/dev/null`, forward slashes). Do **not** run `cd` unless asked.
- Python 3.11+. `fetch.py` and `warera_api.py` auto-install their deps via `_require()` — don't add a separate install step.
- Live API calls need auth: `WARERA_TOKEN` (JWT) or `WARERA_API_KEY` env vars, or `.warera_token` file. Ask the user before running endpoints that require auth if you're unsure which is configured.

## Hard constraints

1. **Backward compatibility is non-negotiable.** Every existing alias (`events`, `articles`/`art`, `battle`, `referrals`/`ref`, `user`, `country`, `region`, `raw`) must keep working with its current flag set. Enrichment only — no removals, no renames.
2. **`specs/` is read-only for this refactor.** If you find schema drift, log it to `docs/cli-design/_spec-audit.md` and move on. Do not edit spec files.
3. **One alias per commit** in Task 3. Message style: `feat(cli): add <alias> for <endpoint>` or `feat(cli): enrich <alias> with <flag>`.
4. **No positional args on aliases.** All input via flags (including `search --query`, not `search Q`). The only exception is `raw <endpoint>` which already exists.
5. **No new synonyms** beyond what the command map lists. Don't add `prices` alongside `market`, don't add `battles` alongside `battle`.
6. **Do not skip the design phase.** Task 3 must not start until Task 2 is complete and the user has reviewed `docs/cli-design/`.

## Testing discipline

- Create `tests/smoke_cli.sh` (or `.py`) in Task 3. One row per alias, each invocation asserts exit 0 and non-empty JSON output. Run it before every commit; never remove rows.
- `pytest tests/` must stay green throughout. If an existing test breaks, stop and ask — don't "fix" it by editing the test.
- For UI/output format changes, actually run the command and paste the output in your update to the user. Don't claim `--humanize` works without seeing it.

## Common gotchas

- `fetch.py` uses `sys.stdout.reconfigure(encoding="utf-8")` on Windows — don't break it.
- tRPC response envelope is `data["result"]["data"]`; `call_endpoint` already unwraps it.
- `warera_api.py` has only a few convenience wrappers; most endpoints go through `call_endpoint(namespace.method, params)` directly. Add wrappers only for endpoints you're giving a new alias.
- Auth precedence in `WaraApiClient.__init__`: `jwt` > legacy `token` > `api_key`. Don't change it.
- `--url` parsing is anchored to `app.warera.io` host (`WARERA_APP_HOST` constant) — reuse the existing parser, don't fork it.

## When to stop and ask

- Any time a design decision isn't in the plan or `docs/cli-design/`.
- Any time you'd need to break an existing alias to make a new one clean.
- Any time the smoke test or pytest regresses.
- Before running destructive shell operations (there shouldn't be any — this refactor is all local edits).

## Output style

- Terse updates between tool calls. State results, not intentions.
- After finishing a task, summarize: what changed, what file list was touched, what the next task is. Don't re-narrate the plan.
