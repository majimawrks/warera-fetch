# tests/test_warera_api.py
import pytest
import httpx
import respx
from warera_api import WaraApiClient

BASE = "https://api2.warera.io/trpc"

@respx.mock
@pytest.mark.asyncio
async def test_get_articles_paginated():
    respx.get(f"{BASE}/article.getArticlesPaginated").mock(return_value=httpx.Response(200, json={
        "result": {"data": {"items": [
            {"_id": "abc123", "title": "Test Article", "content": "<p>Hello</p>",
             "language": "en", "category": "news", "author": "user1",
             "stats": {"likes": 5, "dislikes": 1, "score": 4, "views": 20, "comments": 0, "subs": 0, "tips": 0, "gemTips": 0},
             "publishedAt": "2026-03-14T00:00:00.000Z"}
        ], "nextCursor": None}}
    }))
    async with WaraApiClient() as client:
        result = await client.get_articles_paginated(type="last", limit=1)
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "Test Article"

@respx.mock
@pytest.mark.asyncio
async def test_call_endpoint_generic():
    respx.get(f"{BASE}/country.getAllCountries").mock(return_value=httpx.Response(200, json={
        "result": {"data": [{"_id": "c1", "name": "Testland"}]}
    }))
    async with WaraApiClient() as client:
        result = await client.call_endpoint("country.getAllCountries", {})
    assert result == [{"_id": "c1", "name": "Testland"}]
