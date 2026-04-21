# warera_api.py

Async HTTP client for the Warera tRPC API. All other scripts import this to make API calls.

---

## Role in the project

Pure library — no CLI. Every script that calls the Warera API creates a `WaraApiClient` and calls `call_endpoint()`. The client handles rate-limit retries, authentication headers, and JSON unwrapping so callers don't have to.

---

## Class: `WaraApiClient`

```python
WaraApiClient(debug=False, token=None, jwt=None, api_key=None)
```

Async context manager. Must be used with `async with`:

```python
async with WaraApiClient(jwt="eyJ...", debug=True) as client:
    result = await client.call_endpoint("country.getAllCountries", {})
```

### Constructor parameters

| Parameter | Type | Description |
|---|---|---|
| `debug` | bool | Print every request URL + response status + timing to stderr |
| `token` | str | Alias for `jwt` (legacy, still accepted) |
| `jwt` | str | JWT cookie value — required for protected endpoints (referral.*) |
| `api_key` | str | `X-API-Key` header value — sufficient for public endpoints |

When both `jwt` and `api_key` are provided, JWT takes precedence.

### Methods

#### `call_endpoint(endpoint, params) → any`

The only method you need for most work.

```python
result = await client.call_endpoint("event.getEventsPaginated", {"countryId": "abc123", "limit": 20})
```

- `endpoint`: tRPC path, e.g. `"battle.getById"`, `"itemTrading.getPrices"`
- `params`: dict — serialized as JSON query param `input={"json": params}`
- Returns the unwrapped `result.data.json` value from the tRPC envelope
- Raises `RuntimeError` on HTTP errors or tRPC-level errors
- Retries automatically on HTTP 429 with exponential backoff (up to 5 attempts)

#### Convenience wrappers

These call `call_endpoint` with the fixed params:

```python
await client.get_articles_paginated(type="last", limit=20)
await client.get_article_by_id(article_id="abc123")
await client.get_user_lite(user_id="abc123")
await client.get_country_by_id(country_id="abc123")
await client.get_all_countries()
```

---

## Key constants

| Constant | Value | Notes |
|---|---|---|
| `BASE_URL` | `"https://api2.warera.io/trpc"` | All requests go here |
| `MAX_CONCURRENCY` | `8` | Semaphore — max parallel in-flight requests |
| `MAX_RETRIES` | `5` | 429 retry attempts before giving up |

---

## Auth

Auth is passed directly to the constructor. Headers set:

- With JWT: `Cookie: jwt=<value>` + `Origin: https://app.warera.io` + `Referer: https://app.warera.io/`
- With API key: `X-API-Key: <value>`

Most data-read endpoints (prices, events, articles, battles) work with API key only.
Referral endpoints require JWT.

---

## Dependencies

```
pip: httpx
stdlib: asyncio, json, time, urllib.parse, subprocess, sys
```

Auto-installs `httpx` if missing via `_require()`.

---

## Rate limiting

On HTTP 429, sleeps `2 ** attempt` seconds and retries. After `MAX_RETRIES` exhausted, raises `RuntimeError`.

---

## Error handling

tRPC error shape:
```json
{"error": {"json": {"message": "Not found", "code": -32004}}}
```
The client unwraps this and raises `RuntimeError("Not found")`.

---

## How to extend

**Add a new convenience wrapper:**
```python
async def get_battle_by_id(self, battle_id: str) -> dict:
    return await self.call_endpoint("battle.getById", {"battleId": battle_id})
```

**Call a new endpoint directly:**
```python
result = await client.call_endpoint("someModule.someMethod", {"param": "value"})
```

No other changes needed — the tRPC path is generic.
