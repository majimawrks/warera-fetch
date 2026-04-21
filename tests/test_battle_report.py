# tests/test_battle_report.py
import pytest
import respx
import httpx
import json
import urllib.parse
from fetch import fetch_battle_report, humanize_battle_report

BASE = "https://api2.warera.io/trpc"

# ── Fixture data ──────────────────────────────────────────────────────────────

BATTLE_ID = "aabbcc112233"
REGION_ID = "rr001"
ATT_COUNTRY_ID = "cc_att"
DEF_COUNTRY_ID = "cc_def"
ATT_MU_ID = "mu_att"
DEF_MU_ID = "mu_def"
USER_ATT_ID = "uu_att"
USER_DEF_ID = "uu_def"

BATTLE_DATA = {
    "_id": BATTLE_ID,
    "type": "resistance",
    "isBigBattle": True,
    "war": "war001",
    "roundsToWin": 2,
    "rounds": ["round1", "round2"],
    "roundsHistory": ["attacker"],
    "isActive": True,
    "attacker": {
        "country": ATT_COUNTRY_ID,
        "countryOrders": [ATT_COUNTRY_ID],
        "muOrders": [ATT_MU_ID],
        "damages": 5039881,
        "hitCount": 10000,
        "moneyPer1kDamages": 0.2,
        "moneyPool": 200.0,
    },
    "defender": {
        "region": REGION_ID,
        "country": DEF_COUNTRY_ID,
        "countryOrders": [DEF_COUNTRY_ID],
        "muOrders": [DEF_MU_ID],
        "damages": 4667922,
        "hitCount": 12000,
        "moneyPer1kDamages": 0.25,
        "moneyPool": 96.0,
    },
}

ROUND1_DATA = {
    "battle": {},
    "round": {
        "roundId": "round1",
        "attackerDamages": 5039881,
        "defenderDamages": 4667922,
        "isActive": False,
        "attackerPoints": 303,
        "defenderPoints": 27,
        "nextTickAt": None,
        "actualTickPoints": 4,
    },
}

ROUND2_DATA = {
    "battle": {},
    "round": {
        "roundId": "round2",
        "attackerDamages": 5404930,
        "defenderDamages": 5693711,
        "isActive": True,
        "attackerPoints": 40,
        "defenderPoints": 59,
        "nextTickAt": "2026-03-16T11:23:00.000Z",
        "actualTickPoints": 1,
    },
}

RANKINGS = {
    ("damage", "attacker"): {"rankings": [{"user": USER_ATT_ID, "value": 3064069, "rank": 1, "lootChance": 8000.0}]},
    ("damage", "defender"): {"rankings": [{"user": USER_DEF_ID, "value": 2000000, "rank": 1, "lootChance": 5000.0}]},
    ("points", "attacker"): {"rankings": [{"user": USER_ATT_ID, "value": 303, "rank": 1, "lootChance": 100.0}]},
    ("points", "defender"): {"rankings": [{"user": USER_DEF_ID, "value": 59, "rank": 1, "lootChance": 50.0}]},
}


def _setup_mocks(mock: respx.MockRouter) -> None:
    """Register all expected API calls for a battle report."""
    mock.get(url__startswith=f"{BASE}/battle.getById").mock(
        return_value=httpx.Response(200, json={"result": {"data": BATTLE_DATA}})
    )

    def _round_resp(req):
        raw = urllib.parse.unquote(str(req.url).split("input=")[1])
        params = json.loads(raw)
        rnum = params.get("roundNumber", 1)
        data = ROUND1_DATA if rnum == 1 else ROUND2_DATA
        return httpx.Response(200, json={"result": {"data": data}})

    mock.get(url__startswith=f"{BASE}/battle.getLiveBattleData").mock(side_effect=_round_resp)

    def _ranking_resp(req):
        raw = urllib.parse.unquote(str(req.url).split("input=")[1])
        params = json.loads(raw)
        key = (params["dataType"], params["side"])
        return httpx.Response(200, json={"result": {"data": RANKINGS.get(key, {"rankings": []})}})

    mock.get(url__startswith=f"{BASE}/battleRanking.getRanking").mock(side_effect=_ranking_resp)
    mock.get(url__startswith=f"{BASE}/region.getById").mock(
        return_value=httpx.Response(200, json={"result": {"data": {"name": "Java"}}})
    )
    mock.get(url__startswith=f"{BASE}/mu.getById").mock(
        return_value=httpx.Response(200, json={"result": {"data": {"name": "Mock MU"}}})
    )
    mock.get(url__startswith=f"{BASE}/user.getUserLite").mock(
        return_value=httpx.Response(200, json={"result": {"data": {"username": "MockPlayer"}}})
    )
    mock.get(url__startswith=f"{BASE}/country.getAllCountries").mock(
        return_value=httpx.Response(200, json={"result": {"data": [
            {"_id": ATT_COUNTRY_ID, "name": "Indonesia"},
            {"_id": DEF_COUNTRY_ID, "name": "India"},
        ]}})
    )


@pytest.mark.asyncio
async def test_fetch_battle_report_structure():
    """fetch_battle_report returns a dict with all required top-level keys."""
    with respx.mock:
        _setup_mocks(respx.mock)
        from warera_api import WaraApiClient
        async with WaraApiClient() as client:
            report = await fetch_battle_report(client, BATTLE_ID, show_progress=False)

    required_keys = {
        "battleId", "type", "isBigBattle", "region",
        "attackerCountry", "defenderCountry", "warId",
        "score", "roundsToWin", "isActive",
        "rounds", "bounty",
        "attackerAlliance", "defenderAlliance",
        "attackerMUs", "defenderMUs",
        "topDmgFighters", "topGroundFighters",
    }
    assert required_keys <= set(report.keys()), f"Missing keys: {required_keys - set(report.keys())}"


@pytest.mark.asyncio
async def test_fetch_battle_report_values():
    """Key values are correctly extracted and IDs resolved to names."""
    with respx.mock:
        _setup_mocks(respx.mock)
        from warera_api import WaraApiClient
        async with WaraApiClient() as client:
            report = await fetch_battle_report(client, BATTLE_ID, show_progress=False)

    assert report["region"] == "Java"
    assert report["attackerCountry"] == "Indonesia"
    assert report["defenderCountry"] == "India"
    assert report["type"] == "resistance"
    assert report["isBigBattle"] is True
    assert report["score"] == {"attacker": 1, "defender": 0}
    assert report["roundsToWin"] == 2
    assert len(report["rounds"]) == 2
    assert report["rounds"][0]["winner"] == "attacker"
    assert report["rounds"][1]["winner"] is None
    assert report["bounty"]["attacker"]["per1kDmg"] == 0.2
    assert report["bounty"]["defender"]["per1kDmg"] == 0.25
    assert "Indonesia" in report["attackerAlliance"]
    assert "India" in report["defenderAlliance"]
    assert report["topDmgFighters"]["attacker"][0]["username"] == "MockPlayer"
    assert report["topDmgFighters"]["attacker"][0]["damage"] == 3064069


def test_humanize_battle_report_contains_key_info():
    """humanize_battle_report output contains region, countries, score, and round info."""
    report = {
        "battleId": BATTLE_ID,
        "type": "resistance",
        "isBigBattle": True,
        "region": "Java",
        "attackerCountry": "Indonesia",
        "defenderCountry": "India",
        "warId": "war001",
        "score": {"attacker": 1, "defender": 0},
        "roundsToWin": 2,
        "isActive": True,
        "rounds": [
            {"number": 1, "isActive": False, "winner": "attacker",
             "attackerDmg": 5039881, "defenderDmg": 4667922,
             "attackerPoints": 303, "defenderPoints": 27, "nextTickAt": None},
            {"number": 2, "isActive": True, "winner": None,
             "attackerDmg": 5404930, "defenderDmg": 5693711,
             "attackerPoints": 40, "defenderPoints": 59,
             "nextTickAt": "2026-03-16T11:23:00.000Z"},
        ],
        "bounty": {
            "attacker": {"per1kDmg": 0.2, "pool": 200.0},
            "defender": {"per1kDmg": 0.25, "pool": 96.0},
        },
        "attackerAlliance": ["Indonesia", "Germany"],
        "defenderAlliance": ["India", "France"],
        "attackerMUs": ["MU Alpha"],
        "defenderMUs": ["MU Beta"],
        "topDmgFighters": {
            "attacker": [{"username": "PlayerA", "damage": 3064069}],
            "defender": [{"username": "PlayerX", "damage": 2000000}],
        },
        "topGroundFighters": {
            "attacker": [{"username": "PlayerA", "points": 303}],
            "defender": [{"username": "PlayerX", "points": 59}],
        },
    }
    text = humanize_battle_report(report)

    assert "Java" in text
    assert "Indonesia" in text
    assert "India" in text
    assert "PlayerA" in text
    assert "PlayerX" in text
    assert "Germany" in text
    assert "0.20" in text or "0.2" in text
