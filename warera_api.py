# warera_api.py
import subprocess
import sys


def _require(*packages: tuple) -> None:
    """Auto-install any missing packages.  Each item is (import_name, pip_name)."""
    import importlib
    missing_pip = []
    for import_name, pip_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing_pip.append(pip_name)
    if missing_pip:
        print(f"[setup] Installing: {' '.join(missing_pip)} ...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing_pip],
        )
        print("[setup] Done.", file=sys.stderr)


_require(
    ("httpx", "httpx==0.28.1"),
)

import asyncio
import json
import random
import time
import urllib.parse
from typing import Any
import httpx

BASE_URL = "https://api2.warera.io/trpc"
MAX_CONCURRENCY = 8   # max parallel requests
MAX_RETRIES = 5       # retries on 429


class WaraApiClient:
    def __init__(
        self,
        debug: bool = False,
        token: str | None = None,   # legacy: treated as jwt
        jwt: str | None = None,
        api_key: str | None = None,
    ):
        # `token` is kept for backward-compat; explicit `jwt` takes precedence
        _jwt = (jwt or token or "").strip() or None
        _api_key = (api_key or "").strip() or None

        headers = {
            # Mimic a real browser request — some endpoints (e.g. referral.*) check Origin/Referer.
            "Origin": "https://app.warera.io",
            "Referer": "https://app.warera.io/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if _jwt:
            # JWT session cookie — required for most endpoints; use this when available.
            headers["Cookie"] = f"jwt={_jwt}"
        elif _api_key:
            # API key fallback — only for endpoints that accept it and when no JWT is available.
            headers["X-API-Key"] = _api_key

        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)
        self._sem = asyncio.Semaphore(MAX_CONCURRENCY)
        self._debug = debug
        self._authed = bool(_jwt or _api_key)

        if debug:
            if _jwt:
                print(f"  [debug] auth: Cookie jwt=<{len(_jwt)} chars>", file=sys.stderr)
            elif _api_key:
                print(f"  [debug] auth: X-API-Key=<{len(_api_key)} chars> (no JWT)", file=sys.stderr)
            else:
                print("  [debug] auth: none (unauthenticated)", file=sys.stderr)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    def __del__(self):
        # Best-effort cleanup if the client is abandoned without using a context manager.
        if not self._client.is_closed:
            try:
                import asyncio as _asyncio
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._client.aclose())
                else:
                    loop.run_until_complete(self._client.aclose())
            except Exception:
                pass

    def _dbg(self, msg: str) -> None:
        if self._debug:
            print(f"  [debug] {msg}", file=sys.stderr)

    async def call_endpoint(self, endpoint: str, params: dict) -> Any:
        """Generic caller for any Warera tRPC endpoint, with rate-limit retry."""
        input_json = urllib.parse.quote(json.dumps(params))
        url = f"{BASE_URL}/{endpoint}?input={input_json}"

        async with self._sem:
            for attempt in range(MAX_RETRIES):
                self._dbg(f"GET {endpoint}  params={params}")
                t0 = time.monotonic()
                response = await self._client.get(url)
                elapsed = time.monotonic() - t0

                if response.status_code == 429:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    self._dbg(f"429 rate-limited — retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue

                self._dbg(f"{response.status_code} {elapsed:.2f}s")
                response.raise_for_status()
                data = response.json()
                if "error" in data and "result" not in data:
                    err = data["error"]
                    # tRPC wraps errors in {"error": {"json": {"message": "..."}}}
                    msg = (
                        (err.get("json") or err).get("message", str(err))
                        if isinstance(err, dict) else str(err)
                    )
                    raise ValueError(f"tRPC error: {msg}")
                return data["result"]["data"]

        # All retries exhausted
        response.raise_for_status()

    async def get_articles_paginated(self, **kwargs) -> dict:
        return await self.call_endpoint("article.getArticlesPaginated", kwargs)

    async def get_article_by_id(self, article_id: str) -> dict:
        return await self.call_endpoint("article.getArticleById", {"articleId": article_id})

    async def get_user_lite(self, user_id: str) -> dict:
        return await self.call_endpoint("user.getUserLite", {"userId": user_id})

    async def get_country_by_id(self, country_id: str) -> dict:
        return await self.call_endpoint("country.getCountryById", {"countryId": country_id})

    async def get_all_countries(self) -> list:
        return await self.call_endpoint("country.getAllCountries", {})
