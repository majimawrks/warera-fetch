#!/usr/bin/env bash
# smoke_cli.sh — one row per alias, asserts exit 0 and non-empty JSON output
# Run before every commit in Task 3. Never remove rows.
set -euo pipefail
PYTHON="${PYTHON:-python}"
PASS=0; FAIL=0; SKIP=0

run() {
    local label="$1"; shift
    if out=$("$PYTHON" fetch.py "$@" 2>/dev/null) && [ -n "$out" ]; then
        echo "  PASS  $label"
        ((PASS++)) || true
    else
        echo "  FAIL  $label"
        ((FAIL++)) || true
    fi
}

# run_auth: skips when no API key or JWT token is configured
_WARERA_AUTH="${WARERA_API_KEY:-${WARERA_TOKEN:-}}"
run_auth() {
    local label="$1"; shift
    if [ -z "$_WARERA_AUTH" ]; then
        echo "  SKIP  $label  (no auth — set WARERA_API_KEY to enable)"
        ((SKIP++)) || true
        return
    fi
    run "$label" "$@"
}

echo "=== smoke_cli.sh ==="

# ── existing aliases (backward-compat) ────────────────────────────────────────
run "events"                   events --limit 1
run "ev"                       ev --limit 1
run "articles"                 articles --limit 1
run "art"                      art --article-type top --limit 1
run "country (list)"           country
run "battle (list)"            battle --list --limit 3
run "region (url)"             region --url https://app.warera.io/region/6813b7039403bc4170a5d68a
run "raw"                      raw country.getAllCountries

# ── new aliases ───────────────────────────────────────────────────────────────
run      "regions"             regions
run      "market (all)"        market
run      "market (item)"       market --item grain
run      "mu"                  mu --id 687b12399deb08620c260d86
run      "party"               party --id 698d896724e6e5911b79a8d5
run      "users"               users --country-id 6813b6d546e731854c7ac85c --limit 1
run      "orders"              orders --item grain
run      "sanctions"           sanctions --limit 1
run      "search"              search --query warera
run_auth "ranking (userDamages)"  ranking --type userDamages --limit 1

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
[ "$FAIL" -eq 0 ]
