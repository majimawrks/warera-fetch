#!/usr/bin/env python3
"""fetch.py — Simple CLI to call any Warera tRPC endpoint."""

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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[setup] Done.", file=sys.stderr)


_require(
    ("httpx",           "httpx"),
    ("tqdm",            "tqdm"),
    ("browser_cookie3", "browser-cookie3"),
)

import argparse
import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from tqdm import tqdm
from warera_api import WaraApiClient

# Windows terminals default to cp1252 which can't render UTF-8 box/emoji chars.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VALID_EVENT_TYPES = [
    "warDeclared", "peace_agreement", "battleOpened", "battleEnded",
    "newPresident", "regionTransfer", "peaceMade", "countryMoneyTransfer",
    "depositDiscovered", "depositDepleted", "systemRevolt", "bankruptcy",
    "allianceFormed", "allianceBroken", "regionLiberated",
    "strategicResourcesReshuffled", "resistanceIncreased", "resistanceDecreased",
    "revolutionStarted", "revolutionEnded", "financedRevolt",
]

# ranking.getRanking — metric-based type enum (live API, 2026-04-21)
# The spec previously documented type as "user|country|mu" — that has changed.
VALID_RANKING_TYPES = [
    # country metrics
    "weeklyCountryDamages", "weeklyCountryDamagesPerCitizen", "countryRegionDiff",
    "countryDevelopment", "countryActivePopulation", "countryDamages",
    "countryWealth", "countryProductionBonus", "countryBounty",
    # user metrics
    "weeklyUserDamages", "userDamages", "userWealth", "userLevel",
    "userReferrals", "userSubscribers", "userTerrain", "userPremiumMonths",
    "userPremiumGifts", "userCasesOpened", "userGemsPurchased", "userBounty",
    # mu metrics
    "muWeeklyDamages", "muDamages", "muTerrain", "muWealth", "muBounty",
]

EVENT_ICONS = {
    "warDeclared":                  "⚔️ ",
    "battleOpened":                 "⚔️ ",
    "battleEnded":                  "🏁",
    "peace_agreement":              "🕊️ ",
    "peaceMade":                    "🕊️ ",
    "depositDiscovered":            "🔍",
    "depositDepleted":              "📉",
    "allianceFormed":               "🤝",
    "allianceBroken":               "💔",
    "revolutionStarted":            "🔥",
    "revolutionEnded":              "✅",
    "regionTransfer":               "🗺️ ",
    "regionLiberated":              "🗺️ ",
    "newPresident":                 "👑",
    "systemRevolt":                 "💥",
    "bankruptcy":                   "💸",
    "countryMoneyTransfer":         "💰",
    "financedRevolt":               "💰",
    "resistanceIncreased":          "📈",
    "resistanceDecreased":          "📉",
    "strategicResourcesReshuffled": "🔄",
}

# ── HTML stripping ────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities, returning plain text."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>|</div>|</li>|</h\d>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    entities = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
                "&#39;": "'", "&nbsp;": " "}
    for ent, ch in entities.items():
        text = text.replace(ent, ch)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ── Event formatting ──────────────────────────────────────────────────────────

def format_event(data: dict, country_map: dict, region_map: dict, user_map: dict | None = None) -> str:
    if user_map is None:
        user_map = {}
    t = data.get("type", "unknown")
    c = lambda cid: country_map.get(cid, cid)
    r = lambda rid: region_map.get(rid, rid)
    icon = EVENT_ICONS.get(t, "•")

    if t == "battleOpened":
        attacker = c(data.get("attackerCountry", "?"))
        defender = c(data.get("defenderCountry", "?"))
        region   = r(data.get("defenderRegion", "?"))
        msg = f"Battle opened — {attacker} attacks {defender} in {region}"

    elif t == "battleEnded":
        attacker = c(data.get("attackerCountry", "?"))
        defender = c(data.get("defenderCountry", "?"))
        region   = r(data.get("defenderRegion", data.get("region", "?")))
        msg = f"Battle ended — {attacker} vs {defender} in {region}"

    elif t == "warDeclared":
        attacker = c(data.get("attackerCountry", data.get("country", "?")))
        defender = c(data.get("defenderCountry", data.get("targetCountry", "?")))
        msg = f"War declared — {attacker} → {defender}"

    elif t in ("peaceMade", "peace_agreement"):
        parties = data.get("countries", [])
        c1 = c(parties[0]) if len(parties) > 0 else "?"
        c2 = c(parties[1]) if len(parties) > 1 else "?"
        msg = f"Peace — {c1} and {c2}"

    elif t == "depositDiscovered":
        item   = data.get("itemCode", "?").capitalize()
        bonus  = data.get("bonusPercent", "?")
        region = r(data.get("region", "?"))
        days   = data.get("durationDays", "?")
        msg = f"Deposit discovered — {item} +{bonus}% in {region} ({days} day)"

    elif t == "depositDepleted":
        item   = data.get("itemCode", "?").capitalize()
        region = r(data.get("region", "?"))
        msg = f"Deposit depleted — {item} in {region}"

    elif t == "allianceFormed":
        parties = data.get("countries", [])
        c1 = c(parties[0]) if len(parties) > 0 else "?"
        c2 = c(parties[1]) if len(parties) > 1 else "?"
        msg = f"Alliance formed — {c1} + {c2}"

    elif t == "allianceBroken":
        parties = data.get("countries", [])
        c1 = c(parties[0]) if len(parties) > 0 else "?"
        c2 = c(parties[1]) if len(parties) > 1 else "?"
        msg = f"Alliance broken — {c1} and {c2}"

    elif t == "revolutionStarted":
        country = c(data.get("country", "?"))
        region  = r(data.get("region", "?"))
        msg = f"Revolution started — {country} in {region}"

    elif t == "revolutionEnded":
        country = c(data.get("country", "?"))
        region  = r(data.get("region", "?"))
        msg = f"Revolution ended — {country} in {region}"

    elif t == "regionTransfer":
        region  = r(data.get("region", "?"))
        country = c(data.get("country", data.get("newOwner", "?")))
        msg = f"Region transferred — {region} → {country}"

    elif t == "regionLiberated":
        region  = r(data.get("region", "?"))
        country = c(data.get("country", "?"))
        msg = f"Region liberated — {region} by {country}"

    elif t == "newPresident":
        country = c(data.get("country", "?"))
        user = user_map.get(data.get("user", ""), data.get("user", "?"))
        msg = f"New president — {user} elected in {country}"

    elif t == "systemRevolt":
        country = c(data.get("country", "?"))
        msg = f"System revolt — {country}"

    elif t == "bankruptcy":
        country = c(data.get("country", "?"))
        msg = f"Bankruptcy — {country}"

    elif t == "countryMoneyTransfer":
        src = c(data.get("fromCountry", data.get("country", "?")))
        dst = c(data.get("toCountry", data.get("targetCountry", "?")))
        msg = f"Money transfer — {src} → {dst}"

    elif t == "financedRevolt":
        country = c(data.get("country", "?"))
        target  = c(data.get("targetCountry", ""))
        msg = f"Financed revolt — {country}" + (f" → {target}" if target else "")

    elif t == "resistanceIncreased":
        region = r(data.get("region", "?"))
        msg = f"Resistance increased — {region}"

    elif t == "resistanceDecreased":
        region = r(data.get("region", "?"))
        msg = f"Resistance decreased — {region}"

    elif t == "strategicResourcesReshuffled":
        msg = "Strategic resources reshuffled"

    else:
        msg = f"{t} — {json.dumps(data)}"

    return f"{icon}  {msg}"


# ── Lookup maps ───────────────────────────────────────────────────────────────

async def build_lookup_maps(
    client: WaraApiClient,
    events: list,
    show_progress: bool = False,
) -> tuple[dict, dict, dict]:
    """Return (country_map, region_map, user_map) id→name for all IDs found in events."""
    region_ids = set()
    user_ids = set()
    for e in events:
        d = e.get("data", {})
        for field in ("defenderRegion", "region", "regionId"):
            if field in d:
                region_ids.add(d[field])
        if "user" in d:
            user_ids.add(d["user"])

    all_countries = await client.call_endpoint("country.getAllCountries", {})
    country_map = {c["_id"]: c["name"] for c in all_countries}

    region_map = {}
    with tqdm(region_ids, desc="Resolving regions", unit="region",
              file=sys.stderr, disable=not show_progress, leave=False) as bar:
        for rid in bar:
            try:
                region = await client.call_endpoint("region.getById", {"regionId": rid})
                region_map[rid] = region.get("name", rid)
            except Exception:
                region_map[rid] = rid

    user_map = {}
    with tqdm(user_ids, desc="Resolving users", unit="user",
              file=sys.stderr, disable=not show_progress, leave=False) as bar:
        for uid in bar:
            try:
                user = await client.call_endpoint("user.getUserLite", {"userId": uid})
                user_map[uid] = user.get("username", user.get("login", user.get("name", uid)))
            except Exception:
                user_map[uid] = uid

    return country_map, region_map, user_map


# ── Event humanizer ───────────────────────────────────────────────────────────

def humanize_events(events: list, country_map: dict, region_map: dict, user_map: dict | None = None) -> str:
    if user_map is None:
        user_map = {}
    lines = []
    current_date = None

    for e in events:
        raw_ts = e.get("createdAt", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")) if raw_ts else None
        except ValueError:
            ts = None
        if ts:
            date_str = ts.strftime("%#d %B %Y") if sys.platform == "win32" else ts.strftime("%-d %B %Y")
            time_str = ts.strftime("%H:%M")
        else:
            date_str = "Unknown date"
            time_str = "--:--"

        if date_str != current_date:
            if lines:
                lines.append("")
            lines.append(f"── {date_str} " + "─" * max(0, 44 - len(date_str)))
            current_date = date_str

        event_line = format_event(e.get("data", {}), country_map, region_map, user_map)
        lines.append(f"  {time_str}  {event_line}")

    return "\n".join(lines)


async def fetch_battle_report(
    client: WaraApiClient,
    battle_id: str,
    show_progress: bool = False,
) -> dict:
    """Fetch a complete battle dossier: meta, rounds, rankings, resolved names."""

    # 1 ── Core battle data
    try:
        battle = await client.call_endpoint("battle.getById", {"battleId": battle_id})
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch battle {battle_id}: {exc}") from exc

    att = battle.get("attacker", {})
    defn = battle.get("defender", {})
    rounds_history = battle.get("roundsHistory", [])  # ["attacker", ...] — past round winners
    round_ids = battle.get("rounds", [])               # IDs of active/current rounds
    total_rounds = len(round_ids)  # `rounds` contains ALL round IDs

    # 2 ── Fetch all round live data + 4 rankings concurrently
    round_tasks = [
        client.call_endpoint("battle.getLiveBattleData", {"battleId": battle_id, "roundNumber": n})
        for n in range(1, total_rounds + 1)
    ]
    ranking_combos = [
        ("damage", "attacker"), ("damage", "defender"),
        ("points", "attacker"), ("points", "defender"),
    ]
    ranking_tasks = [
        client.call_endpoint("battleRanking.getRanking", {
            "battleId": battle_id, "dataType": dt, "type": "user", "side": side,
        })
        for dt, side in ranking_combos
    ]

    results = await asyncio.gather(*round_tasks, *ranking_tasks, return_exceptions=True)
    round_results = results[:total_rounds]
    ranking_results = results[total_rounds:]

    # ── Parse round data ──────────────────────────────────────────────────────
    rounds = []
    for i, res in enumerate(round_results, 1):
        past_winner = rounds_history[i - 1] if i <= len(rounds_history) else None
        if isinstance(res, Exception):
            rounds.append({"number": i, "isActive": False, "winner": past_winner,
                           "attackerDmg": 0, "defenderDmg": 0,
                           "attackerPoints": 0, "defenderPoints": 0, "nextTickAt": None})
            continue
        r = res.get("round", {})
        is_active = r.get("isActive", False)
        rounds.append({
            "number": i,
            "isActive": is_active,
            "winner": None if is_active else past_winner,
            "attackerDmg": r.get("attackerDamages", 0),
            "defenderDmg": r.get("defenderDamages", 0),
            "attackerPoints": r.get("attackerPoints", 0),
            "defenderPoints": r.get("defenderPoints", 0),
            "nextTickAt": r.get("nextTickAt") if is_active else None,
        })

    # ── Parse rankings ────────────────────────────────────────────────────────
    def _parse_ranking(res) -> list[dict]:
        if isinstance(res, Exception):
            return []
        return res.get("rankings", []) if isinstance(res, dict) else []

    dmg_att = _parse_ranking(ranking_results[0])
    dmg_def = _parse_ranking(ranking_results[1])
    pts_att = _parse_ranking(ranking_results[2])
    pts_def = _parse_ranking(ranking_results[3])

    # ── Resolve all IDs concurrently ──────────────────────────────────────────
    att_country_id = att.get("country", "")
    def_country_id = defn.get("country", "")
    att_country_orders = att.get("countryOrders", [])
    def_country_orders = defn.get("countryOrders", [])
    att_mu_orders = att.get("muOrders", [])
    def_mu_orders = defn.get("muOrders", [])
    region_id = defn.get("region", "")

    top_user_ids = list({
        r["user"] for ranking in (dmg_att, dmg_def, pts_att, pts_def)
        for r in ranking[:10] if "user" in r
    })
    mu_ids = list(set(att_mu_orders + def_mu_orders))

    try:
        all_countries = await client.call_endpoint("country.getAllCountries", {})
    except Exception as exc:
        print(f"warning: could not fetch country names ({exc}), IDs will appear as-is", file=sys.stderr)
        all_countries = []
    country_map = {c["_id"]: c["name"] for c in all_countries}

    async def safe_region(rid):
        try:
            r = await client.call_endpoint("region.getById", {"regionId": rid})
            return r.get("name", rid)
        except Exception:
            return rid

    async def safe_mu(mid):
        try:
            m = await client.call_endpoint("mu.getById", {"muId": mid})
            return mid, m.get("name", mid)
        except Exception:
            return mid, mid

    async def safe_user(uid):
        try:
            u = await client.call_endpoint("user.getUserLite", {"userId": uid})
            return uid, u.get("username", u.get("login", uid))
        except Exception:
            return uid, uid

    resolution_tasks = [safe_region(region_id)] if region_id else []
    mu_tasks = [safe_mu(mid) for mid in mu_ids]
    user_tasks = [safe_user(uid) for uid in top_user_ids]

    all_resolved = await asyncio.gather(*resolution_tasks, *mu_tasks, *user_tasks,
                                        return_exceptions=True)

    region_name = (
        all_resolved[0]
        if region_id and all_resolved and not isinstance(all_resolved[0], Exception)
        else region_id
    )
    mu_start = len(resolution_tasks)
    mu_end = mu_start + len(mu_ids)
    mu_results = all_resolved[mu_start:mu_end]
    user_results = all_resolved[mu_end:]

    mu_map = {}
    for item in mu_results:
        if not isinstance(item, Exception) and isinstance(item, tuple):
            mu_map[item[0]] = item[1]

    user_map = {}
    for item in user_results:
        if not isinstance(item, Exception) and isinstance(item, tuple):
            user_map[item[0]] = item[1]

    # ── Build alliances (primary country first, no duplicates) ───────────────
    att_alliance = ([country_map.get(att_country_id, att_country_id)] +
                    [country_map.get(cid, cid) for cid in att_country_orders if cid != att_country_id])
    def_alliance = ([country_map.get(def_country_id, def_country_id)] +
                    [country_map.get(cid, cid) for cid in def_country_orders if cid != def_country_id])

    def _top_fighters(ranking: list, value_key: str, limit: int = 10) -> list[dict]:
        return [
            {"username": user_map.get(r["user"], r["user"]), value_key: r["value"]}
            for r in ranking[:limit] if "user" in r
        ]

    return {
        "battleId": battle_id,
        "type": battle.get("type", "unknown"),
        "isBigBattle": battle.get("isBigBattle", False),
        "region": region_name,
        "attackerCountry": country_map.get(att_country_id, att_country_id),
        "defenderCountry": country_map.get(def_country_id, def_country_id),
        "warId": battle.get("war", ""),
        "score": {
            "attacker": rounds_history.count("attacker"),
            "defender": rounds_history.count("defender"),
        },
        "roundsToWin": battle.get("roundsToWin", 2),
        "isActive": battle.get("isActive", False),
        "rounds": rounds,
        "bounty": {
            "attacker": {"per1kDmg": att.get("moneyPer1kDamages", 0), "pool": att.get("moneyPool", 0)},
            "defender": {"per1kDmg": defn.get("moneyPer1kDamages", 0), "pool": defn.get("moneyPool", 0)},
        },
        "attackerAlliance": att_alliance,
        "defenderAlliance": def_alliance,
        "attackerMUs": [mu_map.get(mid, mid) for mid in att_mu_orders],
        "defenderMUs": [mu_map.get(mid, mid) for mid in def_mu_orders],
        "topDmgFighters": {
            "attacker": _top_fighters(dmg_att, "damage"),
            "defender": _top_fighters(dmg_def, "damage"),
        },
        "topGroundFighters": {
            "attacker": _top_fighters(pts_att, "points"),
            "defender": _top_fighters(pts_def, "points"),
        },
    }


def humanize_battle_report(report: dict) -> str:
    """Render a battle dossier dict as a rich, structured text report."""
    lines = []
    SEP  = "═" * 55
    DASH = "─"

    btype  = report.get("type", "unknown").upper()
    region = report.get("region", "?")
    att    = report.get("attackerCountry", "?")
    defn   = report.get("defenderCountry", "?")
    score  = report.get("score", {})
    rtw    = report.get("roundsToWin", 2)
    big    = "  ⚡ BIG BATTLE" if report.get("isBigBattle") else ""
    status = "Active" if report.get("isActive") else "Ended"

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        SEP,
        f"  ⚔️  {btype} BATTLE — {region}{big}",
        f"  {att}  (Attacker)  vs  {defn}  (Defender)",
        f"  Status: {status}",
        SEP,
        "",
    ]

    # ── Score ─────────────────────────────────────────────────────────────────
    lines += [
        f"SCORE   {att} {score.get('attacker', 0)} – {score.get('defender', 0)} {defn}",
        f"        (first to {rtw} round wins)",
        "",
    ]

    # ── Rounds ────────────────────────────────────────────────────────────────
    for rnd in report.get("rounds", []):
        n        = rnd.get("number", "?")
        is_active = rnd.get("isActive", False)
        winner   = rnd.get("winner")
        att_dmg  = rnd.get("attackerDmg", 0)
        def_dmg  = rnd.get("defenderDmg", 0)
        att_pts  = rnd.get("attackerPoints", 0)
        def_pts  = rnd.get("defenderPoints", 0)
        tick     = rnd.get("nextTickAt")

        if is_active:
            hdr = f"── Round {n}  ⚔️  ONGOING " + DASH * 26
        elif winner == "attacker":
            label = f"{att.upper()} WON"
            hdr = f"── Round {n}  ✅ {label} " + DASH * max(0, 40 - len(label))
        elif winner == "defender":
            label = f"{defn.upper()} WON"
            hdr = f"── Round {n}  ✅ {label} " + DASH * max(0, 40 - len(label))
        else:
            hdr = f"── Round {n}  ⏳ PENDING " + DASH * 26

        att_lead = "  ← leading" if is_active and att_pts > def_pts else ""
        def_lead = "  ← leading" if is_active and def_pts > att_pts else ""

        lines += [
            hdr,
            f"  {att:<22} {att_dmg:>12,} dmg   {att_pts:>5} ground pts{att_lead}",
            f"  {defn:<22} {def_dmg:>12,} dmg   {def_pts:>5} ground pts{def_lead}",
        ]
        if tick:
            try:
                ts = datetime.fromisoformat(tick.replace("Z", "+00:00"))
                tick_str = ts.strftime("%H:%M UTC")
            except Exception:
                tick_str = tick
            lines.append(f"  Next tick: {tick_str}")
        lines.append("")

    # ── Alliance orders ───────────────────────────────────────────────────────
    att_alliance = report.get("attackerAlliance", [])
    def_alliance = report.get("defenderAlliance", [])
    if att_alliance or def_alliance:
        lines.append("ALLIANCE ORDERS")
        if att_alliance:
            n = len(att_alliance)
            lines += [
                f"  🟢 {att} side ({n} countr{'y' if n == 1 else 'ies'}):",
                f"     {', '.join(att_alliance)}",
            ]
        if def_alliance:
            n = len(def_alliance)
            lines += [
                f"  🔴 {defn} side ({n} countr{'y' if n == 1 else 'ies'}):",
                f"     {', '.join(def_alliance)}",
            ]
        lines.append("")

    # ── Bounty ────────────────────────────────────────────────────────────────
    bounty = report.get("bounty", {})
    ba = bounty.get("attacker", {})
    bd = bounty.get("defender", {})
    lines += [
        "BOUNTY",
        f"  {att:<22} {ba.get('per1kDmg', 0):.2f} gold / 1k dmg   Pool: {ba.get('pool', 0):.0f}g",
        f"  {defn:<22} {bd.get('per1kDmg', 0):.2f} gold / 1k dmg   Pool: {bd.get('pool', 0):.0f}g",
        "",
    ]

    # ── Top fighters (two-column layout) ──────────────────────────────────────
    COL_W = 38  # left-column width

    def _fighter_row(rank: int, f: dict, value_key: str) -> str:
        name = f.get("username", "?")[:18]
        return f"{rank:>2}. {name:<18} {f.get(value_key, 0):>10,}"

    dmg = report.get("topDmgFighters", {})
    gnd = report.get("topGroundFighters", {})

    for label, section, vkey in [
        ("TOP FIGHTERS — Damage", dmg, "damage"),
        ("TOP FIGHTERS — Ground", gnd, "points"),
    ]:
        left  = section.get("attacker", [])
        right = section.get("defender", [])
        if not left and not right:
            continue
        lines.append(label)
        lines.append(f"  {att:<{COL_W - 2}}  {defn}")
        for i in range(max(len(left), len(right))):
            lf = left[i]  if i < len(left)  else None
            rf = right[i] if i < len(right) else None
            l  = _fighter_row(i + 1, lf, vkey) if lf else ""
            r  = _fighter_row(i + 1, rf, vkey) if rf else ""
            lines.append(f"  {l:<{COL_W - 2}}  {r}")
        lines.append("")

    # ── MU orders (two-column layout) ─────────────────────────────────────────
    att_mus = report.get("attackerMUs", [])
    def_mus = report.get("defenderMUs", [])
    if att_mus or def_mus:
        lines.append("MILITARY UNIT ORDERS")
        att_hdr = f"{att} ({len(att_mus)} MUs):" if att_mus else ""
        def_hdr = f"{defn} ({len(def_mus)} MUs):" if def_mus else ""
        lines.append(f"  {att_hdr:<{COL_W - 2}}  {def_hdr}")
        for i in range(max(len(att_mus), len(def_mus))):
            l = f"• {att_mus[i]}" if i < len(att_mus) else ""
            r = f"• {def_mus[i]}" if i < len(def_mus) else ""
            lines.append(f"  {l:<{COL_W - 2}}  {r}")
        lines.append("")

    return "\n".join(lines)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _fatal(msg: str) -> None:
    """Print an error message to stderr and exit with code 1.

    Centralised so callers can raise a testable exception instead of calling
    sys.exit() directly in library code.  Replace with ``raise FatalError(msg)``
    when a proper exception hierarchy is added.
    """
    print(msg, file=sys.stderr)
    sys.exit(1)


# ── Warera URL parser ─────────────────────────────────────────────────────────

WARERA_APP_HOST = "app.warera.io"

# Maps the entity-type segment of a Warera URL to the tRPC param name expected by most endpoints.
URL_PARAM_MAP: dict[str, str] = {
    "battle":   "battleId",
    "article":  "articleId",
    "country":  "countryId",
    "user":     "userId",
    "region":   "regionId",
    "mu":       "muId",
    "party":    "partyId",
    "referral": "referralId",
}

def parse_warera_url(url: str) -> tuple[str, str] | None:
    """Extract (entity_type, entity_id) from a Warera app URL.

    Examples:
      https://app.warera.io/battle/69b75f41...  → ("battle", "69b75f41...")
      https://app.warera.io/country/6813b6d5... → ("country", "6813b6d5...")
      https://app.warera.io/user/abc123         → ("user", "abc123")

    Returns None if the URL is not a recognised Warera app URL.
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if parsed.hostname != WARERA_APP_HOST:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1]   # (entity_type, entity_id)


# ── Article fetching by country ───────────────────────────────────────────────

async def fetch_articles_by_country(
    client: WaraApiClient,
    country_id: str,
    limit: int,
    article_type: str,
    languages: list[str] | None,
    show_progress: bool = False,
) -> tuple[list[dict], dict]:
    """
    Fetch articles globally in batches, resolve author countries concurrently,
    keep only articles whose author belongs to country_id.
    Returns (articles, user_map).
    """
    BATCH = 100
    MAX_PAGES = 10
    user_cache: dict[str, dict] = {}
    collected: list[dict] = []
    cursor = None

    async def get_user(uid: str) -> dict:
        if uid not in user_cache:
            try:
                user_cache[uid] = await client.call_endpoint("user.getUserLite", {"userId": uid})
            except Exception:
                user_cache[uid] = {}
        return user_cache[uid]

    article_bar = tqdm(
        total=limit, desc="Collecting articles", unit="article",
        file=sys.stderr, disable=not show_progress,
    )
    scan_bar = tqdm(
        desc="Scanning authors", unit="author",
        file=sys.stderr, disable=not show_progress, leave=False,
    )

    try:
        for page in range(1, MAX_PAGES + 1):
            params: dict = {"type": article_type, "limit": BATCH}
            if languages:
                params["languages"] = languages
            if cursor:
                params["cursor"] = cursor

            if show_progress:
                scan_bar.set_description(f"Fetching batch {page}/{MAX_PAGES}")

            result = await client.call_endpoint("article.getArticlesPaginated", params)
            items = result.get("items", []) if isinstance(result, dict) else result

            if not items:
                break

            # Resolve all authors in this batch concurrently
            unique_authors = list({a.get("author", "") for a in items if a.get("author")})
            new_authors = [uid for uid in unique_authors if uid not in user_cache]
            await asyncio.gather(*[get_user(uid) for uid in new_authors])
            scan_bar.update(len(new_authors))

            for article in items:
                author_id = article.get("author", "")
                user = user_cache.get(author_id, {})
                if user.get("country") == country_id:
                    collected.append(article)
                    article_bar.update(1)
                    if len(collected) >= limit:
                        break

            if show_progress:
                scan_bar.set_postfix({"total_scanned": len(user_cache), "found": len(collected)})

            if len(collected) >= limit:
                break

            cursor = result.get("nextCursor") if isinstance(result, dict) else None
            if not cursor:
                break
    finally:
        article_bar.close()
        scan_bar.close()

    print(
        f"found {len(collected)} article(s) — scanned {len(user_cache)} unique authors",
        file=sys.stderr,
    )

    user_map = {
        uid: u.get("username", uid)
        for uid, u in user_cache.items()
        if u.get("country") == country_id
    }

    return collected[:limit], user_map


async def fetch_articles_by_user(
    client: "WaraApiClient",
    user_id: str,
    limit: int,
    article_type: str,
    languages: list[str] | None,
    show_progress: bool = False,
) -> tuple[list[dict], dict]:
    """
    Fetch articles by a specific author (client-side filter on article.author == user_id).
    Returns (articles, user_map).
    """
    BATCH = 100
    MAX_PAGES = 10
    collected: list[dict] = []
    cursor = None
    username = user_id

    try:
        user_profile = await client.call_endpoint("user.getUserLite", {"userId": user_id})
        username = user_profile.get("username", user_id)
    except Exception:
        pass

    article_bar = tqdm(
        total=limit, desc=f"Collecting articles by {username}", unit="article",
        file=sys.stderr, disable=not show_progress,
    )

    pages_scanned = 0
    try:
        for _page in range(1, MAX_PAGES + 1):
            params: dict = {"type": article_type, "limit": BATCH}
            if languages:
                params["languages"] = languages
            if cursor:
                params["cursor"] = cursor

            result = await client.call_endpoint("article.getArticlesPaginated", params)
            items = result.get("items", []) if isinstance(result, dict) else result
            pages_scanned += 1

            if not items:
                break

            for article in items:
                if article.get("author") == user_id:
                    collected.append(article)
                    article_bar.update(1)
                    if len(collected) >= limit:
                        break

            if len(collected) >= limit:
                break

            cursor = result.get("nextCursor") if isinstance(result, dict) else None
            if not cursor:
                break
    finally:
        article_bar.close()

    if len(collected) < limit and pages_scanned >= MAX_PAGES:
        print(
            f"warning: scanned {pages_scanned * BATCH} global articles "
            f"(page cap reached) but found only {len(collected)} by {username}. "
            "Results may be incomplete — the author may have fewer articles than requested.",
            file=sys.stderr,
        )
    else:
        print(f"found {len(collected)} article(s) by {username}", file=sys.stderr)
    return collected[:limit], {user_id: username}


# ── User referral fetching ────────────────────────────────────────────────────


async def fetch_user_referrals(
    client: WaraApiClient,
    user_id: str,
    limit: int,
    show_progress: bool = False,
) -> tuple[dict, list[dict]]:
    """
    Fetch user profile and their referral list.
    Returns (user_profile, referrals, country_map) where referrals are resolved with username/country.
    """
    # Fetch user profile and first page of referrals concurrently
    profile_task = client.call_endpoint("user.getUserLite", {"userId": user_id})
    referrals_task = client.call_endpoint(
        "referral.getUserReferralsPaginated",
        {"userId": user_id, "limit": limit},
    )

    profile_result, referrals_result = await asyncio.gather(
        profile_task, referrals_task, return_exceptions=True
    )

    profile: dict = {}
    if isinstance(profile_result, Exception):
        print(f"warning: could not fetch user profile: {profile_result}", file=sys.stderr)
    else:
        profile = profile_result or {}

    # Normalise referral result: handle both array and paginated {items:[...]}
    def _extract_list(data) -> list:
        """Best-effort extraction of a list from whatever the API returns."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Try common envelope keys in priority order
            for key in ("items", "referrals", "data", "users"):
                val = data.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict) and val:
                    # Could be a nested envelope like {"items": [...]} — recurse
                    inner = _extract_list(val)
                    if inner:
                        return inner
                    # Fall back: treat dict values as the items themselves
                    # (handles {"0": {...}, "1": {...}} object-of-objects shape)
                    return list(val.values())
        return []

    raw_referrals: list = []
    if isinstance(referrals_result, Exception):
        # Fall back to non-paginated endpoint
        try:
            fallback = await client.call_endpoint(
                "referral.getUserReferrals", {"userId": user_id}
            )
            raw_referrals = _extract_list(fallback)
        except Exception as exc:
            print(f"warning: referral fetch failed: {exc}", file=sys.stderr)
            raw_referrals = []
    else:
        raw_referrals = _extract_list(referrals_result)

    raw_referrals = raw_referrals[:limit]

    async def resolve_referral(entry) -> dict:
        if isinstance(entry, str):
            uid = entry
        elif isinstance(entry, dict):
            # If it already looks like a user object with a username, return as-is
            if entry.get("username") or entry.get("login"):
                return entry

            # Check if a nested user object is embedded (e.g. referredUser: {_id, username, ...})
            for field in ("referredUser", "user"):
                val = entry.get(field)
                if isinstance(val, dict):
                    if val.get("username") or val.get("login"):
                        return val          # already resolved
                    nested_id = val.get("_id") or val.get("id") or ""
                    if nested_id:
                        uid = nested_id
                        break
            else:
                # Prefer referral-record user-ID fields over the record's own _id
                uid = (
                    entry.get("referredUserId")
                    or entry.get("userId")
                    or (entry.get("referredUser") if isinstance(entry.get("referredUser"), str) else None)
                    or (entry.get("user") if isinstance(entry.get("user"), str) else None)
                    or entry.get("id")
                    or entry.get("_id")
                    or ""
                )
        else:
            return {}

        if not uid:
            return entry if isinstance(entry, dict) else {}
        try:
            u = await client.call_endpoint("user.getUserLite", {"userId": uid})
            return u or {}
        except Exception:
            return {"_id": uid}

    with tqdm(
        total=len(raw_referrals), desc="Resolving referrals", unit="user",
        file=sys.stderr, disable=not show_progress, leave=False,
    ) as bar:
        resolved: list[dict] = []
        tasks = [resolve_referral(r) for r in raw_referrals]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            resolved.append(result)
            bar.update(1)

    # Sort by join date (createdAt) ascending so list is chronological
    def _join_ts(u: dict) -> str:
        return u.get("createdAt", "")

    resolved.sort(key=_join_ts)

    # Fetch all countries once for name resolution
    try:
        all_countries = await client.call_endpoint("country.getAllCountries", {})
        country_map = {c["_id"]: c["name"] for c in all_countries}
    except Exception:
        country_map = {}

    return profile, resolved, country_map


def humanize_user_referrals(user_id: str, profile: dict, referrals: list[dict], country_map: dict) -> str:
    """Render a user profile + referral list as a structured text block."""
    SEP = "═" * 55
    lines = []

    username = profile.get("username", profile.get("login", user_id))
    country_id = profile.get("country", "")
    country_name = country_map.get(country_id, country_id)
    level = profile.get("level", "")
    xp = profile.get("xp", profile.get("experience", ""))
    joined = profile.get("createdAt", "")
    if joined:
        try:
            ts = datetime.fromisoformat(joined.replace("Z", "+00:00"))
            joined = ts.strftime("%#d %B %Y") if sys.platform == "win32" else ts.strftime("%-d %B %Y")
        except Exception:
            pass

    lines += [
        SEP,
        f"  👤  {username}",
        f"  Country : {country_name}",
    ]
    if level:
        lines.append(f"  Level   : {level}" + (f"  ({xp} XP)" if xp else ""))
    if joined:
        lines.append(f"  Joined  : {joined}")
    lines += [SEP, ""]

    n = len(referrals)
    lines.append(f"REFERRALS  ({n} total)")
    if not referrals:
        lines.append("  (none)")
    else:
        lines.append("  " + "─" * 50)
        for i, ref in enumerate(referrals, 1):
            ref_uid  = ref.get("_id", "")
            ref_name = ref.get("username", ref.get("login", ref_uid or "?"))
            ref_cid = ref.get("country", "")
            ref_country = country_map.get(ref_cid, ref_cid) if ref_cid else ""
            ref_joined = ref.get("createdAt", "")
            if ref_joined:
                try:
                    ts = datetime.fromisoformat(ref_joined.replace("Z", "+00:00"))
                    ref_joined = ts.strftime("%#d %B %Y") if sys.platform == "win32" else ts.strftime("%-d %B %Y")
                except Exception:
                    pass
            uid_str     = f" ({ref_uid})" if ref_uid else ""
            country_str = f"  [{ref_country}]" if ref_country else ""
            joined_str  = f"  joined {ref_joined}" if ref_joined else ""
            lines.append(f"  {i:>3}. {ref_name}{uid_str}{country_str}{joined_str}")

    lines.append("")
    return "\n".join(lines)


# ── Article humanizer ─────────────────────────────────────────────────────────

def fmt_article_date(iso: str) -> str:
    if not iso:
        return "unknown date"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return ts.strftime("%#d %B %Y") if sys.platform == "win32" else ts.strftime("%-d %B %Y")
    except ValueError:
        return "unknown date"


def humanize_articles(articles: list[dict], user_map: dict) -> str:
    blocks = []
    for a in articles:
        date   = fmt_article_date(a.get("publishedAt", a.get("createdAt", "")))
        author = user_map.get(a.get("author", ""), a.get("author", "unknown"))
        title  = a.get("title", "")
        body   = strip_html(a.get("content", ""))

        block = f"date: {date}\nauthor: {author}\ntitle: {title}\n\n{body}"
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def _fmt_date(iso: str) -> str:
    """Format an ISO timestamp to a human-readable date string."""
    if not iso:
        return "—"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return ts.strftime("%#d %B %Y") if sys.platform == "win32" else ts.strftime("%-d %B %Y")
    except Exception:
        return iso


def humanize_user(data: dict, country_map: dict | None = None) -> str:
    SEP = "═" * 55
    country_id = data.get("country", "")
    country_name = (country_map or {}).get(country_id, country_id) if country_id else "—"
    level = data.get("level", "")
    xp = data.get("xp", data.get("experience", ""))
    lines = [
        SEP,
        f"  👤  {data.get('username', data.get('login', data.get('_id', '?')))}",
        f"  Country : {country_name}",
    ]
    if level:
        lines.append(f"  Level   : {level}" + (f"  ({xp} XP)" if xp else ""))
    joined = _fmt_date(data.get("createdAt", ""))
    if joined != "—":
        lines.append(f"  Joined  : {joined}")
    lines.append(SEP)
    return "\n".join(lines)


def humanize_country(data: dict) -> str:
    SEP = "═" * 55
    lines = [
        SEP,
        f"  🌐  {data.get('name', '?')}  [{data.get('code', '')}]",
        f"  ID      : {data.get('_id', '—')}",
    ]
    if data.get("rulingParty"):
        lines.append(f"  Party   : {data['rulingParty']}")
    if data.get("allies"):
        lines.append(f"  Allies  : {len(data['allies'])}")
    if data.get("warsWith"):
        lines.append(f"  Wars    : {len(data['warsWith'])}")
    lines.append(SEP)
    return "\n".join(lines)


def humanize_region(data: dict, country_map: dict | None = None) -> str:
    SEP = "═" * 55
    country_id = data.get("country", "")
    country_name = (country_map or {}).get(country_id, country_id) if country_id else "—"
    lines = [
        SEP,
        f"  🗺   {data.get('name', '?')}  [{data.get('code', '')}]",
        f"  ID      : {data.get('_id', '—')}",
        f"  Country : {country_name}",
        f"  Capital : {'yes' if data.get('isCapital') else 'no'}",
        f"  Biome   : {data.get('biome', '—')}",
        f"  Climate : {data.get('climate', '—')}",
    ]
    lines.append(SEP)
    return "\n".join(lines)


def humanize_mu(data: dict) -> str:
    SEP = "═" * 55
    lines = [
        SEP,
        f"  ⚔️   {data.get('name', '?')}",
        f"  ID      : {data.get('_id', '—')}",
        f"  Country : {data.get('country', '—')}",
        f"  Leader  : {data.get('leader', data.get('leaderId', '—'))}",
        f"  Members : {data.get('membersCount', data.get('members', '—'))}",
    ]
    lines.append(SEP)
    return "\n".join(lines)


def humanize_party(data: dict) -> str:
    SEP = "═" * 55
    lines = [
        SEP,
        f"  🏛️   {data.get('name', '?')}",
        f"  ID      : {data.get('_id', '—')}",
        f"  Country : {data.get('country', '—')}",
        f"  Leader  : {data.get('leader', data.get('leaderId', '—'))}",
        f"  Members : {data.get('membersCount', data.get('members', '—'))}",
    ]
    lines.append(SEP)
    return "\n".join(lines)


def humanize_market(data: dict) -> str:
    """Render market prices as a compact two-column table."""
    SEP = "═" * 55
    lines = [SEP, "  MARKET PRICES", "  " + "─" * 50]
    if isinstance(data, dict):
        for item_code, prices in sorted(data.items()):
            if isinstance(prices, dict):
                buy  = prices.get("buy",  prices.get("buyPrice",  "—"))
                sell = prices.get("sell", prices.get("sellPrice", "—"))
                lines.append(f"  {item_code:<20}  buy: {buy:<10}  sell: {sell}")
            else:
                lines.append(f"  {item_code:<20}  {prices}")
    else:
        lines.append(f"  {data}")
    lines.append(SEP)
    return "\n".join(lines)


def humanize_orders(data: dict, item_code: str = "") -> str:
    """Render top buy/sell orders as two labelled sections."""
    SEP = "═" * 55
    lines = [SEP, f"  ORDERS  —  {item_code.upper()}", ""]

    def _render_orders(label: str, orders: list) -> None:
        lines.append(f"  {label}")
        lines.append("  " + "─" * 50)
        if not orders:
            lines.append("  (none)")
        else:
            for o in orders[:10]:
                price = o.get("price", o.get("unitPrice", "?"))
                qty   = o.get("quantity", o.get("amount", "?"))
                owner = o.get("ownerId", o.get("owner", ""))
                owner_str = f"  [{owner}]" if owner else ""
                lines.append(f"    price: {price:<12}  qty: {qty}{owner_str}")
        lines.append("")

    buy_orders  = data.get("buyOrders",  []) if isinstance(data, dict) else []
    sell_orders = data.get("sellOrders", []) if isinstance(data, dict) else []
    _render_orders("BUY ORDERS", buy_orders)
    _render_orders("SELL ORDERS", sell_orders)
    lines.append(SEP)
    return "\n".join(lines)


def humanize_search(data: dict, query: str = "") -> str:
    """Render search results grouped by entity type."""
    SEP = "═" * 55
    lines = [SEP, f"  SEARCH  —  {query!r}", ""]
    if not isinstance(data, dict):
        lines += [f"  {data}", SEP]
        return "\n".join(lines)

    has_data = data.get("hasData", False)
    if not has_data:
        lines += ["  (no results)", SEP]
        return "\n".join(lines)

    for key in ("userIds", "muIds", "countryIds", "regionIds", "partyIds"):
        ids: list = data.get(key, [])
        if ids:
            label = key[:-1] if key.endswith("s") else key  # crude singularize
            lines.append(f"  {key} ({len(ids)})")
            for i in ids[:5]:
                lines.append(f"    {i}")
            if len(ids) > 5:
                lines.append(f"    … and {len(ids) - 5} more")
            lines.append("")
    lines.append(SEP)
    return "\n".join(lines)


def articles_to_json(articles: list[dict], user_map: dict) -> list[dict]:
    out = []
    for a in articles:
        out.append({
            "date":    a.get("publishedAt", a.get("createdAt", "")),
            "author":  user_map.get(a.get("author", ""), a.get("author", "unknown")),
            "title":   a.get("title", ""),
            "content": strip_html(a.get("content", "")),
            "language": a.get("language", ""),
            "category": a.get("category", ""),
        })
    return out


# ── Output saving ─────────────────────────────────────────────────────────────

def resolve_format(args: "argparse.Namespace", out_path: str | None) -> str:
    """Determine the output format: --format wins, then path extension, then 'txt' if --humanize, else 'json'."""
    if args.format:
        return args.format
    if out_path and out_path != "AUTO":
        ext = Path(out_path).suffix.lower().lstrip(".")
        if ext in ("txt", "md", "json"):
            return ext
    if getattr(args, "humanize", False):
        return "txt"
    return "json"


def auto_output_path(args: "argparse.Namespace", entity_id: str | None = None) -> str:
    """Build a default filename when --output is given without a value."""
    cmd = getattr(args, "command", "raw")
    endpoint = getattr(args, "endpoint", "")

    _prefix_by_cmd = {
        "events": "events", "ev": "events",
        "articles": "article", "art": "article",
        "battle": "battle", "bat": "battle",
        "referrals": "referrals", "ref": "referrals",
        "user": "user",
        "country": "country",
        "region": "region",
        "regions": "regions",
        "market": "market",
        "orders": "orders",
        "mu": "mu",
        "party": "party",
        "users": "users",
        "sanctions": "sanctions", "bans": "sanctions",
        "search": "search",
        "ranking": "ranking",
    }
    prefix = _prefix_by_cmd.get(cmd)
    if not prefix:
        if "article" in endpoint:
            prefix = "article"
        elif "event" in endpoint:
            prefix = "events"
        elif "battle" in endpoint:
            prefix = "battle"
        elif "country" in endpoint:
            prefix = "country"
        elif "user" in endpoint:
            prefix = "user"
        else:
            prefix = endpoint.split(".")[-1] if endpoint else "output"

    if entity_id:
        ident = entity_id
    elif getattr(args, "url", None):
        parsed = parse_warera_url(args.url)
        ident = parsed[1] if parsed else "unknown"
    elif getattr(args, "country", None):
        ident = args.country.lower().replace(" ", "-")
    elif getattr(args, "country_id", None):
        ident = args.country_id
    else:
        ident = "output"

    # Use the resolved format (honours --humanize → txt) rather than defaulting to json
    fmt = resolve_format(args, None)
    return f"output/{prefix}-{ident}.{fmt}"


def save_output(content: str | list, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".json":
        p.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        p.write_text(content if isinstance(content, str) else str(content), encoding="utf-8")
    print(f"saved → {p.resolve()}", file=sys.stderr)


# ── Argument parser ───────────────────────────────────────────────────────────

def _add_auth_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("authentication")
    g.add_argument(
        "--api-key", metavar="KEY", default=None, dest="api_key",
        help=(
            "X-API-Key token from Settings → API Tokens. "
            "Can also be set via WARERA_API_KEY env var or .warera_token file."
        ),
    )
    g.add_argument(
        "--jwt", metavar="TOKEN", default=None,
        help=(
            "[DANGEROUS] JWT cookie value. Using your session JWT may get your account banned. "
            "A confirmation prompt will be shown before use. "
            "Prefer --api-key for all normal operations."
        ),
    )


def _add_output_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("output")
    g.add_argument("--humanize", action="store_true", help="Format output as human-readable text")
    g.add_argument(
        "--output", nargs="?", const="AUTO", default=None, metavar="FILE",
        help=(
            "Save output to file. "
            "Bare --output auto-names as output/<entity>-<id>.<fmt>."
        ),
    )
    g.add_argument(
        "--format", choices=["txt", "md", "json"], default=None, metavar="FMT",
        help="Output format: txt, md, or json (default: json). Overrides path extension.",
    )
    g.add_argument("--raw", action="store_true", help="Print raw JSON (no pretty-print)")
    g.add_argument("--debug", action="store_true", help="Print every API call and timing to stderr")
    g.add_argument("--progress", action="store_true", help="Show progress bars while fetching")


def _add_country_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("country filter")
    g.add_argument("--country", metavar="NAME", help="Country name (case-insensitive)")
    g.add_argument("--country-id", metavar="ID", dest="country_id", help="Country ID (raw)")


def _add_limit_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--limit", type=int, metavar="N", default=None, help="Number of results (default: 10)")
    p.add_argument("--cursor", metavar="CURSOR", help="Pagination cursor")


_AUTH_EPILOG = """
authentication:
  --api-key KEY         X-API-Key from Settings → API Tokens  (recommended)
  WARERA_API_KEY=KEY    set X-API-Key via env var
  .warera_token file    JSON with "api_key" field (recommended for persistent use)

  .warera_token format:
    {
      "api_key": "wra_..."        <- from Settings → API Tokens
    }

  JWT (session cookie) — use only when API key is insufficient:
  --jwt TOKEN           pass JWT value directly  [shows confirmation prompt]
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch.py",
        description="Fetch data from the Warera tRPC API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run 'python fetch.py COMMAND --help' for per-command options.\n\n"
            "tip: pass a Warera URL as the first argument to auto-detect the command:\n"
            "  python fetch.py https://app.warera.io/battle/<id> --humanize\n"
        ),
    )

    subs = parser.add_subparsers(dest="command", metavar="COMMAND")
    subs.required = True

    # ── events ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "events", aliases=["ev"],
        help="In-game event feed (wars, battles, elections, …)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch the in-game news feed.",
        epilog=(
            "examples:\n"
            "  python fetch.py events --country Indonesia --limit 20 --humanize\n"
            "  python fetch.py events --country Indonesia --event-types warDeclared allianceFormed\n"
            "  python fetch.py events --country Indonesia --humanize --output events.md\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="event.getEventsPaginated", params="{}")
    _add_country_args(p)
    p.add_argument("--url", metavar="URL", help="Warera app URL (entity ID is injected automatically)")
    _add_limit_args(p)
    g = p.add_argument_group("event filters")
    g.add_argument(
        "--event-types", nargs="+", metavar="TYPE", choices=VALID_EVENT_TYPES,
        help="Filter by event type(s): " + ", ".join(VALID_EVENT_TYPES),
    )
    _add_output_args(p)
    _add_auth_args(p)

    # ── articles ──────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "articles", aliases=["art"],
        help="News articles — list (by country/author/language) or single",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Fetch articles.\n\n"
            "routing (first match wins):\n"
            "  --url <article URL> or --id  → single article (getArticleById / getArticleLiteById)\n"
            "  --uname USERNAME             → articles by that author\n"
            "  --country NAME               → articles by authors from that country\n"
            "  --language LANG [LANG …]     → articles in those languages (global)\n"
            "  (no filters)                 → recent global feed"
        ),
        epilog=(
            "examples:\n"
            "  python fetch.py articles --country Indonesia --limit 10 --humanize\n"
            "  python fetch.py articles --url https://app.warera.io/article/<id> --humanize\n"
            "  python fetch.py articles --id <article-id> --humanize\n"
            "  python fetch.py articles --uname majima --humanize\n"
            "  python fetch.py articles --uname majima --country Indonesia --humanize\n"
            "  python fetch.py articles --language id --limit 20\n"
            "  python fetch.py articles --country Indonesia --language id --output articles.md\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="article.getArticlesPaginated", params="{}")
    _add_country_args(p)
    p.add_argument("--url", metavar="URL", help="Warera article URL → fetches that single article")
    p.add_argument("--id", metavar="ID", dest="article_id", default=None, help="Article ID → fetches that single article")
    p.add_argument("--uname", metavar="USERNAME", help="Filter articles by author username")
    _add_limit_args(p)
    g = p.add_argument_group("article filters")
    g.add_argument(
        "--article-type", metavar="TYPE",
        choices=["daily", "weekly", "top", "my", "subscriptions", "last"],
        default="last", help="Feed type (default: last)",
    )
    g.add_argument("--language", nargs="+", metavar="LANG", help="Language codes (e.g. id en)")
    g.add_argument("--lite", action="store_true", help="Use getArticleLiteById to fetch full raw objects (reveals all fields incl. votes)")
    _add_output_args(p)
    _add_auth_args(p)

    # ── battle ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "battle", aliases=["bat"],
        help="Full battle dossier, or list battles with --list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch a complete battle report (default) or list battles (--list).",
        epilog=(
            "examples:\n"
            "  python fetch.py battle --id <battleId> --humanize\n"
            "  python fetch.py battle --country Indonesia --humanize\n"
            "  python fetch.py battle --url https://app.warera.io/battle/<id> --humanize\n"
            "  python fetch.py battle --list --active --limit 5\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="battle.getReport", params="{}")
    p.add_argument("--id", metavar="ID", dest="battle_id", default=None,
                   help="Battle ID (MongoDB ObjectID) — direct dossier lookup")
    p.add_argument("--url", metavar="URL", help="Warera battle URL")
    _add_country_args(p)
    p.add_argument("--list", action="store_true", dest="battle_list",
                   help="List mode: fetch battle list (battle.getBattles) instead of a single report")
    p.add_argument("--active", action="store_true",
                   help="(--list mode) Filter to active battles only (isActive: true)")
    _add_limit_args(p)
    _add_output_args(p)
    _add_auth_args(p)

    # ── referrals ─────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "referrals", aliases=["ref"],
        help="User referral list (requires authentication)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch a user's referral list.\n\nRequires authentication (JWT cookie).",
        epilog=(
            "examples:\n"
            "  python fetch.py referrals --url https://app.warera.io/user/<id> --humanize\n"
            "  python fetch.py referrals --uname majima --humanize\n"
            "  python fetch.py referrals --uname majima --country Indonesia --humanize\n"
            "  python fetch.py referrals --uname majima --output referrals.txt\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="referral.getUserReferrals", params="{}")
    _add_country_args(p)
    p.add_argument("--url", metavar="URL", help="Warera user URL")
    p.add_argument("--uname", metavar="USERNAME", help="Look up user by username")
    _add_limit_args(p)
    _add_output_args(p)
    _add_auth_args(p)

    # ── user ──────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "user",
        help="Player profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch a player profile.",
        epilog=(
            "examples:\n"
            "  python fetch.py user --url https://app.warera.io/user/<id>\n"
            "  python fetch.py user --id <userId>\n"
            "  python fetch.py user --uname majima\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="user.getUserLite", params="{}")
    p.add_argument("--id", metavar="ID", dest="user_id", default=None,
                   help="User ID (MongoDB ObjectID)")
    p.add_argument("--url", metavar="URL", help="Warera user URL")
    p.add_argument("--uname", metavar="USERNAME", help="Look up user by username")
    _add_output_args(p)
    _add_auth_args(p)

    # ── country ───────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "country",
        help="Country detail, or list all countries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Fetch country info.\n\n"
            "  With --id, --name, or --url  → fetch one country's detail\n"
            "  With no args                 → list all countries"
        ),
        epilog=(
            "examples:\n"
            "  python fetch.py country --name Indonesia\n"
            "  python fetch.py country --id <countryId>\n"
            "  python fetch.py country --url https://app.warera.io/country/<id>\n"
            "  python fetch.py country\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="country.getCountryById", params="{}")
    p.add_argument("--id", metavar="ID", dest="country_id", default=None,
                   help="Country ID (MongoDB ObjectID)")
    p.add_argument("--name", metavar="NAME", dest="country_name", default=None,
                   help="Country name (case-insensitive substring match)")
    p.add_argument("--url", metavar="URL", help="Warera country URL")
    _add_output_args(p)
    _add_auth_args(p)

    # ── region ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "region",
        help="Region detail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch region info.",
        epilog=(
            "examples:\n"
            "  python fetch.py region --url https://app.warera.io/region/<id>\n"
            "  python fetch.py region --id <regionId>\n"
            "  python fetch.py region --country Indonesia\n"
            + _AUTH_EPILOG
        ),
    )
    p.set_defaults(endpoint="region.getById", params="{}")
    p.add_argument("--id", metavar="ID", dest="region_id", default=None,
                   help="Region ID (MongoDB ObjectID)")
    p.add_argument("--url", metavar="URL", help="Warera region URL")
    _add_country_args(p)
    _add_output_args(p)
    _add_auth_args(p)

    # ── regions ───────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "regions",
        help="All regions as a flat object keyed by region ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch all regions (region.getRegionsObject). No params.",
        epilog="examples:\n  python fetch.py regions\n  python fetch.py regions --output\n" + _AUTH_EPILOG,
    )
    _add_output_args(p)
    _add_auth_args(p)

    # ── market ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "market",
        help="Current market prices for all items (or a single item)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch market prices (itemTrading.getPrices).",
        epilog=(
            "examples:\n"
            "  python fetch.py market\n"
            "  python fetch.py market --item grain\n"
            "  python fetch.py market --humanize\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--item", metavar="CODE", default=None,
                   help="Item code to filter (e.g. grain, oil, iron). Omit for all prices.")
    _add_output_args(p)
    _add_auth_args(p)

    # ── orders ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "orders",
        help="Top buy/sell orders for an item",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch top trading orders (tradingOrder.getTopOrders).",
        epilog=(
            "examples:\n"
            "  python fetch.py orders --item grain\n"
            "  python fetch.py orders --item oil --humanize\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--item", metavar="CODE", required=True,
                   help="Item code (e.g. grain, oil, iron, steel).")
    _add_output_args(p)
    _add_auth_args(p)

    # ── mu ────────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "mu",
        help="Military unit profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch a military unit (mu.getById).",
        epilog=(
            "examples:\n"
            "  python fetch.py mu --id <muId>\n"
            "  python fetch.py mu --url https://app.warera.io/mu/<id>\n"
            "  python fetch.py mu --id <muId> --humanize\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--id", metavar="ID", dest="mu_id", default=None, help="MU ID (MongoDB ObjectID)")
    p.add_argument("--url", metavar="URL", help="Warera MU URL")
    _add_output_args(p)
    _add_auth_args(p)

    # ── party ─────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "party",
        help="Political party profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch a political party (party.getById).",
        epilog=(
            "examples:\n"
            "  python fetch.py party --id <partyId>\n"
            "  python fetch.py party --url https://app.warera.io/party/<id>\n"
            "  python fetch.py party --id <partyId> --humanize\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--id", metavar="ID", dest="party_id", default=None, help="Party ID (MongoDB ObjectID)")
    p.add_argument("--url", metavar="URL", help="Warera party URL")
    _add_output_args(p)
    _add_auth_args(p)

    # ── users ─────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "users",
        help="List users in a country",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch users by country (user.getUsersByCountry).",
        epilog=(
            "examples:\n"
            "  python fetch.py users --country Indonesia\n"
            "  python fetch.py users --country-id <id> --limit 50\n"
            + _AUTH_EPILOG
        ),
    )
    _add_country_args(p)
    _add_limit_args(p)
    _add_output_args(p)
    _add_auth_args(p)

    # ── sanctions / bans ──────────────────────────────────────────────────────
    p = subs.add_parser(
        "sanctions", aliases=["bans"],
        help="Paginated list of sanctions/bans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Fetch sanctions (sanction.getPaginated).",
        epilog=(
            "examples:\n"
            "  python fetch.py sanctions --limit 10\n"
            "  python fetch.py bans --uname someuser\n"
            "  python fetch.py sanctions --user-id <id> --limit 20\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--user-id", metavar="ID", dest="target_user_id", default=None,
                   help="Filter by target user ID (maps to targetUserId API param).")
    p.add_argument("--uname", metavar="USERNAME", default=None,
                   help="Resolve username to user ID for filtering.")
    p.add_argument("--direction", metavar="DIR", default=None,
                   help="Sort/pagination direction (e.g. asc, desc).")
    p.add_argument("--limit", type=int, metavar="N", default=None, help="Max results.")
    _add_output_args(p)
    _add_auth_args(p)

    # ── search ────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "search",
        help="Search for users, MUs, countries, regions, parties",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Search anything (search.searchAnything). Returns IDs grouped by entity type.",
        epilog=(
            "examples:\n"
            "  python fetch.py search --query warera\n"
            "  python fetch.py search --query Indonesia --humanize\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--query", metavar="Q", required=True,
                   help="Search term. Maps to 'searchText' API param.")
    _add_output_args(p)
    _add_auth_args(p)

    # ── ranking ───────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "ranking",
        help="Global metric rankings or in-battle rankings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Fetch rankings.\n\n"
            "  --type <metric>  → ranking.getRanking  (global; 25 metric types)\n"
            "  --type battle    → battleRanking.getRanking  (requires --battle-id, --entity, --side)"
        ),
        epilog=(
            "examples:\n"
            "  python fetch.py ranking --type userDamages --limit 20\n"
            "  python fetch.py ranking --type countryWealth\n"
            "  python fetch.py ranking --type muBounty\n"
            "  python fetch.py ranking --type battle --battle-id <id> --entity user --side merged\n"
            "  python fetch.py ranking --type battle --battle-url https://app.warera.io/battle/<id> --entity country --side attacker --data-type points\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("--type", metavar="TYPE", required=True,
                   choices=VALID_RANKING_TYPES + ["battle"],
                   help=(
                       "Ranking metric (e.g. userDamages, countryWealth, muBounty …) "
                       "or 'battle' for battle rankings. "
                       "Full list: " + ", ".join(VALID_RANKING_TYPES)
                   ))
    p.add_argument("--limit", type=int, metavar="N", default=None,
                   help="Max results (global rankings only).")
    p.add_argument("--battle-id", metavar="ID", dest="battle_id", default=None,
                   help="Battle ID (--type battle).")
    p.add_argument("--battle-url", metavar="URL", dest="battle_url", default=None,
                   help="Battle URL (--type battle, alternative to --battle-id).")
    p.add_argument("--entity", metavar="TYPE", default=None,
                   choices=["user", "country", "mu"],
                   help="Entity type to rank within battle (--type battle): user, country, or mu.")
    p.add_argument("--side", metavar="SIDE", default=None,
                   choices=["attacker", "defender", "merged"],
                   help="Battle side (--type battle): attacker, defender, or merged.")
    p.add_argument("--data-type", metavar="TYPE", dest="data_type", default="damage",
                   choices=["damage", "points"],
                   help="Metric for battle rankings: damage (default) or points.")
    _add_output_args(p)
    _add_auth_args(p)

    # ── raw ───────────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "raw",
        help="Call any tRPC endpoint directly (power-user escape hatch)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Call any Warera tRPC endpoint with raw JSON params.",
        epilog=(
            "examples:\n"
            "  python fetch.py raw event.getEventsPaginated --params '{\"countryId\":\"abc\"}'\n"
            "  python fetch.py raw country.getAllCountries\n"
            "  python fetch.py raw ranking.getRanking --params '{\"type\":\"user\"}'\n"
            "  python fetch.py raw battle.getBattles --params '{\"isActive\":true,\"limit\":5}'\n"
            + _AUTH_EPILOG
        ),
    )
    p.add_argument("endpoint", help="tRPC endpoint (e.g. event.getEventsPaginated)")
    p.add_argument("--params", metavar="JSON", default="{}", help="Raw JSON params for the endpoint")
    _add_country_args(p)
    p.add_argument("--url", metavar="URL", help="Warera app URL (entity ID injected automatically)")
    _add_limit_args(p)
    g = p.add_argument_group("event options (for event.getEventsPaginated)")
    g.add_argument(
        "--event-types", nargs="+", metavar="TYPE", choices=VALID_EVENT_TYPES,
        help="Filter by event type(s)",
    )
    _add_output_args(p)
    _add_auth_args(p)

    return parser


def build_params(args: argparse.Namespace, resolved_country_id: str | None = None) -> dict:
    try:
        params = json.loads(getattr(args, "params", "{}"))
    except json.JSONDecodeError as exc:
        print(f"error: --params is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    cmd = getattr(args, "command", "raw")
    is_article = cmd in ("articles", "art")

    # ── Inject entity ID from --url for generic endpoint calls ────────────────
    if getattr(args, "url", None):
        parsed_url = parse_warera_url(args.url)
        if parsed_url:
            entity_type, entity_id = parsed_url
            param_key = URL_PARAM_MAP.get(entity_type)
            if param_key and param_key not in params:
                params[param_key] = entity_id
                print(f"info: injected {param_key}={entity_id!r} from URL", file=sys.stderr)

    if not is_article:
        if resolved_country_id:
            params["countryId"] = resolved_country_id
        elif getattr(args, "country_id", None):
            params["countryId"] = args.country_id

    limit = getattr(args, "limit", None)
    if limit is not None:
        params["limit"] = limit
    elif "limit" not in params:
        params["limit"] = 10
    if getattr(args, "cursor", None):
        params["cursor"] = args.cursor
    if getattr(args, "event_types", None):
        params["eventTypes"] = args.event_types

    if is_article:
        params["type"] = getattr(args, "article_type", "last")
        if getattr(args, "language", None):
            params["languages"] = args.language

    return params


async def resolve_country_name(client: WaraApiClient, name: str) -> str:
    countries = await client.call_endpoint("country.getAllCountries", {})
    needle = name.lower()
    matches = [c for c in countries if c.get("name", "").lower() == needle]
    if not matches:
        matches = [c for c in countries if needle in c.get("name", "").lower()]
    if not matches:
        names = ", ".join(c.get("name", "") for c in countries)
        _fatal(f"error: no country matching '{name}'. Available:\n  {names}")
    if len(matches) > 1:
        ambiguous = ", ".join(f"{c['name']} ({c['_id']})" for c in matches)
        _fatal(f"error: ambiguous country name '{name}', matches: {ambiguous}")
    return matches[0]["_id"]


async def resolve_user_by_name(client: WaraApiClient, username: str, country_id: str | None = None) -> str:
    """Look up a user ID by username via search.searchAnything.

    Searches by searchText, retrieves the userIds list, then fetches each
    profile to find an exact (or substring) match.  If country_id is provided,
    results are filtered to that country.  Exits with an error message if no
    unique match is found.
    """
    try:
        raw = await client.call_endpoint("search.searchAnything", {"searchText": username})
    except Exception as exc:
        _fatal(f"error: search failed: {exc}")

    # API returns {"userIds": [...], "muIds": [], "countryIds": [], ...}
    user_ids: list[str] = raw.get("userIds", []) if isinstance(raw, dict) else []

    if not user_ids:
        _fatal(f"error: no user found matching username '{username}'")

    # Fetch all candidate profiles concurrently
    async def _safe_user(uid: str) -> dict | None:
        try:
            return await client.call_endpoint("user.getUserLite", {"userId": uid})
        except Exception:
            return None

    profiles = await asyncio.gather(*[_safe_user(uid) for uid in user_ids])
    candidates = [u for u in profiles if u is not None]

    needle = username.lower()
    # Exact match first, then substring
    exact   = [u for u in candidates if (u.get("username") or "").lower() == needle]
    matches = exact or [u for u in candidates if needle in (u.get("username") or "").lower()]

    if country_id:
        filtered = [u for u in matches if u.get("country") == country_id]
        if filtered:
            matches = filtered

    if not matches:
        _fatal(f"error: no user found matching username '{username}'")
    if len(exact) > 1:
        names = ", ".join(
            f"{u.get('username', '?')} ({u.get('_id', '?')})"
            for u in exact[:5]
        )
        _fatal(
            f"error: multiple accounts share username '{username}': {names}\n"
            "  Use --url https://app.warera.io/user/<id> to target one specifically."
        )
    if len(matches) > 1 and not exact:
        names = ", ".join(
            f"{u.get('username', '?')} ({u.get('_id', '?')})"
            for u in matches[:5]
        )
        _fatal(f"error: ambiguous username '{username}', matches: {names}")

    user = (exact or matches)[0]
    uid  = user.get("_id") or user.get("id")
    if not uid:
        _fatal("error: could not extract user ID from search result")
    print(f"info: resolved '{username}' → {uid}", file=sys.stderr)
    return uid


# ── Main ──────────────────────────────────────────────────────────────────────

def resolve_output(args: argparse.Namespace, entity_id: str | None = None) -> str | None:
    """Return the resolved output path, or None if --output was not given."""
    if args.output is None:
        return None
    if args.output == "AUTO":
        return auto_output_path(args, entity_id)
    return args.output


def _jwt_expiry_info(token: str) -> tuple[bool, int | None]:
    """Decode a JWT (no signature check) and return (is_still_valid, seconds_remaining).

    Returns (True, None) when the token can't be decoded or has no exp claim.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return True, None
        padding = 4 - len(parts[1]) % 4
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
        payload = json.loads(payload_bytes)
        exp = payload.get("exp")
        if exp is None:
            return True, None
        remaining = int(exp) - int(time.time())
        return remaining > 0, remaining
    except Exception:
        return True, None


def _jwt_from_browser() -> str | None:
    """Try to read the 'jwt' cookie for warera.io from the running browser profile.

    Supports Chrome, Firefox, Edge, and Firefox-fork browsers (Floorp, Zen, LibreWolf, etc.)
    Requires the optional package:  pip install browser-cookie3
    Returns None (silently) if the package is missing or the cookie isn't found.
    """
    try:
        import browser_cookie3  # type: ignore
    except ImportError:
        return None

    # Standard browsers first
    for loader in (browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge):
        try:
            jar = loader(domain_name="warera.io")
            for cookie in jar:
                if cookie.name == "jwt" and cookie.value:
                    return cookie.value
        except Exception:
            continue

    # Firefox-fork browsers: same SQLite cookie format, just different AppData paths.
    # Look inside each fork's Profiles/ directory for a cookies.sqlite, then use
    # browser_cookie3.firefox(cookie_file=...) to read it exactly like real Firefox.
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()

    firefox_fork_roots: list[Path] = []
    for base in (appdata, localappdata):
        if base:
            for fork in ("Floorp", "Zen Browser", "LibreWolf", "Waterfox", "Pale Moon", "IceCat"):
                firefox_fork_roots.append(Path(base) / fork / "Profiles")
    # Linux / macOS variants (harmless to check on Windows)
    for fork_dir in (".floorp", ".zen", ".librewolf", ".waterfox"):
        firefox_fork_roots.append(home / fork_dir)

    for profiles_dir in firefox_fork_roots:
        if not profiles_dir.exists():
            continue
        # Prefer most-recently-modified profile (the active one)
        try:
            profiles = sorted(
                [p for p in profiles_dir.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            continue
        for profile in profiles:
            cookie_db = profile / "cookies.sqlite"
            if not cookie_db.exists():
                continue
            try:
                jar = browser_cookie3.firefox(
                    cookie_file=str(cookie_db), domain_name="warera.io"
                )
                for cookie in jar:
                    if cookie.name == "jwt" and cookie.value:
                        return cookie.value
            except Exception:
                continue

    return None


# Resolve token file path once at import time, relative to this script's directory.
# This ensures the file is found regardless of the user's working directory.
_TOKEN_FILE = Path(__file__).parent / ".warera_token"


def _confirm_jwt_use() -> None:
    """Prompt the user to confirm JWT use. Exits if they decline."""
    print(
        "\n⚠️  WARNING: Using your session JWT cookie may get your account banned.\n"
        "   The game server can detect automated requests made with a session token.\n"
        "   Use --api-key with your API key from Settings → API Tokens instead.\n",
        file=sys.stderr,
    )
    try:
        answer = input("Continue with JWT anyway? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer != "y":
        print("Aborted.", file=sys.stderr)
        sys.exit(1)


def resolve_token(args: argparse.Namespace) -> dict:
    """Return auth credentials as {"jwt": ..., "api_key": ...} (values may be None).

    JWT is only sourced from an explicit --jwt flag.
    API key sources (in priority order):
      1. --api-key CLI flag
      2. WARERA_API_KEY env var
      3. .warera_token file  {"api_key": "wra_..."}
    """
    creds: dict = {"jwt": None, "api_key": None}

    # JWT — explicit --jwt flag only; never auto-loaded from env/file/browser
    if getattr(args, "jwt", None):
        creds["jwt"] = args.jwt.strip()

    # Warn if WARERA_TOKEN is set but --jwt was not passed
    if not creds["jwt"] and os.environ.get("WARERA_TOKEN", "").strip():
        print(
            "info: WARERA_TOKEN env var is set but JWT auth is disabled by default. "
            "Pass --jwt to enable JWT (confirmation required).",
            file=sys.stderr,
        )

    # API key — flag → env var → file
    if getattr(args, "api_key", None):
        creds["api_key"] = args.api_key.strip()

    if not creds["api_key"]:
        env_key = os.environ.get("WARERA_API_KEY", "").strip()
        if env_key:
            creds["api_key"] = env_key

    if not creds["api_key"]:
        if _TOKEN_FILE.exists():
            raw = _TOKEN_FILE.read_text(encoding="utf-8").strip()
            if raw:
                try:
                    data = json.loads(raw)
                    creds["api_key"] = (data.get("api_key") or "").strip() or None
                except json.JSONDecodeError:
                    pass  # legacy plain-text files contained a JWT — ignore silently

    # Validate JWT expiry if one was explicitly provided
    if creds["jwt"]:
        valid, remaining = _jwt_expiry_info(creds["jwt"])
        if not valid:
            print(
                "warning: the provided JWT has expired. Protected endpoints will fail.\n"
                "  Get a fresh token: DevTools → Network → any api2 request → Cookie → jwt=",
                file=sys.stderr,
            )
        elif remaining is not None and remaining < 3600:
            mins = remaining // 60
            print(
                f"warning: JWT expires in {mins} minute(s). Consider refreshing soon.",
                file=sys.stderr,
            )

    return creds


def _url_autodispatch() -> None:
    """If sys.argv[1] is a Warera URL, inject the matching subcommand and --url flag.

    Lets users run:  python fetch.py https://app.warera.io/battle/<id> --humanize
    instead of:      python fetch.py battle --url https://app.warera.io/battle/<id> --humanize
    """
    if len(sys.argv) < 2:
        return
    first = sys.argv[1]
    if not (first.startswith("https://") or first.startswith("http://")):
        return
    if "warera.io" not in first:
        return
    parsed = parse_warera_url(first)
    if not parsed:
        return
    entity_type = parsed[0]
    cmd_map = {
        "battle":  "battle",
        "article": "articles",
        "user":    "user",
        "country": "country",
        "region":  "region",
        "mu":      "mu",
        "party":   "party",
        "referral": None,       # no dedicated subcommand; use: referrals --url …
    }
    cmd = cmd_map.get(entity_type)
    if cmd is None:
        if entity_type in cmd_map:
            # Known entity type but no subcommand — give a helpful hint
            hints = {
                "referral": "referrals --url",
            }
            hint = hints.get(entity_type, f"raw <endpoint> --url")
            print(
                f"info: '{entity_type}' URLs are not auto-dispatched. "
                f"Use: python fetch.py {hint} {first}",
                file=sys.stderr,
            )
        return
    rest = sys.argv[2:]
    sys.argv[1:] = [cmd, "--url", first] + rest
    print(f"info: auto-detected {entity_type} URL → 'fetch.py {cmd} --url …'", file=sys.stderr)


async def main() -> None:
    _url_autodispatch()

    parser = build_parser()
    args = parser.parse_args()
    cmd = args.command

    creds = resolve_token(args)

    if creds["jwt"]:
        _confirm_jwt_use()

    async with WaraApiClient(
        debug=getattr(args, "debug", False),
        jwt=creds["jwt"],
        api_key=creds["api_key"],
    ) as client:

        # Resolve --country name → ID (shared across all subcommands)
        resolved_country_id: str | None = None
        if getattr(args, "country", None):
            resolved_country_id = await resolve_country_name(client, args.country)

        # ── events ────────────────────────────────────────────────────────────
        if cmd in ("events", "ev"):
            params = build_params(args, resolved_country_id)
            try:
                result = await client.call_endpoint("event.getEventsPaginated", params)
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                events = result.get("items", result) if isinstance(result, dict) else result
                country_map, region_map, user_map = await build_lookup_maps(
                    client, events, show_progress=args.progress
                )
                text = humanize_events(events, country_map, region_map, user_map)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── articles ──────────────────────────────────────────────────────────
        if cmd in ("articles", "art"):
            # Determine routing mode
            article_id = getattr(args, "article_id", None)
            if not article_id and getattr(args, "url", None):
                parsed_url = parse_warera_url(args.url)
                if parsed_url and parsed_url[0] == "article":
                    article_id = parsed_url[1]

            # ── Single article ──
            if article_id:
                use_lite = getattr(args, "lite", False)
                endpoint = "article.getArticleLiteById" if use_lite else "article.getArticleById"
                try:
                    article = await client.call_endpoint(
                        endpoint, {"articleId": article_id}
                    )
                except Exception as exc:
                    print(f"error: could not fetch article {article_id}: {exc}", file=sys.stderr)
                    sys.exit(1)

                author_id = article.get("author", "")
                author_name = author_id
                if author_id:
                    try:
                        u = await client.call_endpoint("user.getUserLite", {"userId": author_id})
                        author_name = u.get("username", author_id)
                    except Exception:
                        pass

                user_map = {author_id: author_name}
                articles = [article]

                out_path = resolve_output(args, entity_id=article_id)
                fmt = resolve_format(args, out_path)
                if args.humanize or out_path:
                    if fmt == "json":
                        data = articles_to_json(articles, user_map)
                        text = json.dumps(data, indent=2, ensure_ascii=False)
                        if out_path:
                            save_output(data, out_path)
                        else:
                            print(text)
                    else:
                        text = humanize_articles(articles, user_map)
                        if out_path:
                            save_output(text, out_path)
                        else:
                            print(text)
                elif args.raw:
                    print(json.dumps(article))
                else:
                    print(json.dumps(article, indent=2, ensure_ascii=False))
                return

            # ── Articles by author / country / global ──
            articles: list[dict] = []
            user_map: dict = {}
            uname = getattr(args, "uname", None)
            if uname:
                user_id = await resolve_user_by_name(
                    client, uname,
                    country_id=resolved_country_id or getattr(args, "country_id", None),
                )
                articles, user_map = await fetch_articles_by_user(
                    client, user_id,
                    (args.limit or 10), args.article_type,
                    getattr(args, "language", None),
                    show_progress=args.progress,
                )

            # ── Articles by country ──
            elif resolved_country_id or getattr(args, "country_id", None):
                cid = resolved_country_id or args.country_id
                articles, user_map = await fetch_articles_by_country(
                    client, cid, (args.limit or 10), args.article_type,
                    getattr(args, "language", None),
                    show_progress=args.progress,
                )

            # ── Global feed (language filter or no filter) ──
            else:
                params: dict = {"type": args.article_type, "limit": args.limit or 10}
                if getattr(args, "language", None):
                    params["languages"] = args.language
                if getattr(args, "cursor", None):
                    params["cursor"] = args.cursor
                try:
                    result = await client.call_endpoint("article.getArticlesPaginated", params)
                except Exception as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    sys.exit(1)
                items = result.get("items", []) if isinstance(result, dict) else result
                articles = items
                user_map = {}

            # ── Lite enrichment: replace articles with getArticleLiteById results ──
            if getattr(args, "lite", False) and articles:
                async def _fetch_lite(aid: str) -> dict | None:
                    try:
                        return await client.call_endpoint("article.getArticleLiteById", {"articleId": aid})
                    except Exception:
                        return None

                ids = [a.get("_id") or a.get("id", "") for a in articles]
                lite_results = await asyncio.gather(*[_fetch_lite(aid) for aid in ids if aid])
                articles = [r for r in lite_results if r is not None]
                out_path = resolve_output(args)
                if out_path:
                    save_output(articles, out_path)
                elif args.raw:
                    print(json.dumps(articles))
                else:
                    print(json.dumps(articles, indent=2, ensure_ascii=False))
                return

            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_articles(articles, user_map)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                data = articles_to_json(articles, user_map)
                if out_path:
                    save_output(data, out_path)
                elif args.raw:
                    print(json.dumps(data))
                else:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        # ── battle ────────────────────────────────────────────────────────────
        if cmd in ("battle", "bat"):

            # ── List mode (--list) ──
            if getattr(args, "battle_list", False):
                list_params: dict = {}
                if getattr(args, "active", False):
                    list_params["isActive"] = True
                cid = resolved_country_id or getattr(args, "country_id", None)
                if cid:
                    list_params["countryId"] = cid
                if getattr(args, "limit", None) is not None:
                    list_params["limit"] = args.limit
                try:
                    result = await client.call_endpoint("battle.getBattles", list_params)
                except Exception as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    sys.exit(1)
                out_path = resolve_output(args)
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                return

            # ── Dossier mode ──
            battle_id = getattr(args, "battle_id", None)
            if battle_id:
                print(f"info: using battle ID {battle_id}", file=sys.stderr)
            elif getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed is None or parsed[0] != "battle":
                    print(
                        "error: --url does not look like a battle URL "
                        "(expected https://app.warera.io/battle/<id>)",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                battle_id = parsed[1]
                print(f"info: using battle ID {battle_id} from URL", file=sys.stderr)
            else:
                if not (resolved_country_id or getattr(args, "country_id", None)):
                    print(
                        "error: battle requires --id ID, --url URL, "
                        "--country NAME, or --country-id ID",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                cid = resolved_country_id or args.country_id
                battles_result = await client.call_endpoint(
                    "battle.getBattles", {"isActive": True, "limit": 50, "countryId": cid}
                )
                battles = (
                    battles_result.get("items", [])
                    if isinstance(battles_result, dict)
                    else battles_result
                )
                if not battles:
                    print("error: no active battle found for this country", file=sys.stderr)
                    sys.exit(1)
                if len(battles) > 1:
                    other_ids = ", ".join(b["_id"] for b in battles[1:])
                    print(
                        f"info: {len(battles)} active battles found, using first. Others: {other_ids}",
                        file=sys.stderr,
                    )
                battle_id = battles[0]["_id"]

            report = await fetch_battle_report(client, battle_id, show_progress=args.progress)

            out_path = resolve_output(args, entity_id=battle_id)
            fmt = resolve_format(args, out_path)
            if args.humanize or out_path:
                if fmt == "json":
                    text = json.dumps(report, indent=2, ensure_ascii=False)
                else:
                    text = humanize_battle_report(report)
                if out_path:
                    save_output(report if fmt == "json" else text, out_path)
                else:
                    print(text)
            elif args.raw:
                print(json.dumps(report))
            else:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            return

        # ── referrals ─────────────────────────────────────────────────────────
        if cmd in ("referrals", "ref"):
            if not creds["jwt"]:
                print(
                    "warning: referral endpoints require authentication (JWT cookie).\n"
                    "  Pass your JWT with:  --jwt <token>\n"
                    "  Get your JWT: DevTools → Network → any api2 request → Cookie header → value after 'jwt='\n"
                    "  Note: using JWT risks account ban. Use only when necessary.",
                    file=sys.stderr,
                )

            user_id = None
            if getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "user":
                    user_id = parsed[1]
            if not user_id and getattr(args, "uname", None):
                user_id = await resolve_user_by_name(
                    client, args.uname,
                    country_id=resolved_country_id or getattr(args, "country_id", None),
                )
            if not user_id:
                try:
                    raw_p = json.loads(getattr(args, "params", "{}"))
                    user_id = raw_p.get("userId")
                except Exception:
                    pass
            if not user_id:
                print(
                    "error: referrals requires a user.\n"
                    "  Use --url https://app.warera.io/user/<id>\n"
                    "  or  --uname USERNAME [--country NAME]",
                    file=sys.stderr,
                )
                sys.exit(1)

            profile, referrals, country_map = await fetch_user_referrals(
                client, user_id, args.limit or 50, show_progress=args.progress
            )

            out_path = resolve_output(args, entity_id=user_id)
            fmt = resolve_format(args, out_path)

            if args.humanize or (out_path and fmt != "json"):
                text = humanize_user_referrals(user_id, profile, referrals, country_map)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                data = {
                    "userId": user_id,
                    "profile": profile,
                    "referrals": referrals,
                    "totalReferrals": len(referrals),
                }
                if out_path:
                    save_output(data, out_path)
                elif args.raw:
                    print(json.dumps(data))
                else:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        # ── user ──────────────────────────────────────────────────────────────
        if cmd == "user":
            user_id = getattr(args, "user_id", None)
            if not user_id and getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "user":
                    user_id = parsed[1]
            if not user_id and getattr(args, "uname", None):
                user_id = await resolve_user_by_name(client, args.uname)
            if not user_id:
                print(
                    "error: user requires --id ID, --url URL, or --uname USERNAME",
                    file=sys.stderr,
                )
                sys.exit(1)

            try:
                result = await client.call_endpoint("user.getUserLite", {"userId": user_id})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            out_path = resolve_output(args, entity_id=user_id)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── country ───────────────────────────────────────────────────────────
        if cmd == "country":
            cid = getattr(args, "country_id", None)
            if not cid and getattr(args, "country_name", None):
                cid = await resolve_country_name(client, args.country_name)
            if not cid and getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "country":
                    cid = parsed[1]

            try:
                if cid:
                    result = await client.call_endpoint("country.getCountryById", {"countryId": cid})
                else:
                    result = await client.call_endpoint("country.getAllCountries", {})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            out_path = resolve_output(args, entity_id=cid)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── region ────────────────────────────────────────────────────────────
        if cmd == "region":
            region_id = getattr(args, "region_id", None)
            if not region_id and getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "region":
                    region_id = parsed[1]
            if not region_id and (resolved_country_id or getattr(args, "country_id", None)):
                # Resolve country → find its capital region via getRegionsObject
                cid = resolved_country_id or args.country_id
                try:
                    all_regions = await client.call_endpoint("region.getRegionsObject", {})
                    capital = next(
                        (
                            (rid, rv)
                            for rid, rv in all_regions.items()
                            if isinstance(rv, dict) and rv.get("country") == cid and rv.get("isCapital")
                        ),
                        None,
                    )
                    if capital:
                        region_id = capital[0]
                        print(f"info: using capital region {region_id} for country {cid}", file=sys.stderr)
                    else:
                        print(f"error: no capital region found for country {cid}", file=sys.stderr)
                        sys.exit(1)
                except Exception as exc:
                    print(f"error: could not resolve capital region: {exc}", file=sys.stderr)
                    sys.exit(1)
            if not region_id:
                print(
                    "error: region requires --id ID, --url URL, --country NAME, or --country-id ID",
                    file=sys.stderr,
                )
                sys.exit(1)

            try:
                result = await client.call_endpoint("region.getById", {"regionId": region_id})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            out_path = resolve_output(args, entity_id=region_id)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── regions ───────────────────────────────────────────────────────────
        if cmd == "regions":
            try:
                result = await client.call_endpoint("region.getRegionsObject", {})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── market ────────────────────────────────────────────────────────────
        if cmd == "market":
            try:
                result = await client.call_endpoint("itemTrading.getPrices", {})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            # Client-side filter: API returns all prices regardless of itemCode param
            if getattr(args, "item", None) and isinstance(result, dict):
                item_key = args.item.lower()
                result = {k: v for k, v in result.items() if k.lower() == item_key}
                if not result:
                    print(f"error: item '{args.item}' not found in market prices", file=sys.stderr)
                    sys.exit(1)
            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_market(result)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── orders ────────────────────────────────────────────────────────────
        if cmd == "orders":
            try:
                result = await client.call_endpoint(
                    "tradingOrder.getTopOrders", {"itemCode": args.item}
                )
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_orders(result, args.item)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── mu ────────────────────────────────────────────────────────────────
        if cmd == "mu":
            mu_id = getattr(args, "mu_id", None)
            if not mu_id and getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "mu":
                    mu_id = parsed[1]
            if not mu_id:
                print("error: mu requires --id ID or --url URL", file=sys.stderr)
                sys.exit(1)
            try:
                result = await client.call_endpoint("mu.getById", {"muId": mu_id})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args, entity_id=mu_id)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_mu(result)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── party ─────────────────────────────────────────────────────────────
        if cmd == "party":
            party_id = getattr(args, "party_id", None)
            if not party_id and getattr(args, "url", None):
                parsed = parse_warera_url(args.url)
                if parsed and parsed[0] == "party":
                    party_id = parsed[1]
            if not party_id:
                print("error: party requires --id ID or --url URL", file=sys.stderr)
                sys.exit(1)
            try:
                result = await client.call_endpoint("party.getById", {"partyId": party_id})
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args, entity_id=party_id)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_party(result)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── users ─────────────────────────────────────────────────────────────
        if cmd == "users":
            cid = resolved_country_id or getattr(args, "country_id", None)
            user_params: dict = {}
            if cid:
                user_params["countryId"] = cid
            if getattr(args, "limit", None) is not None:
                user_params["limit"] = args.limit
            if getattr(args, "cursor", None):
                user_params["cursor"] = args.cursor
            try:
                result = await client.call_endpoint("user.getUsersByCountry", user_params)
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── sanctions / bans ──────────────────────────────────────────────────
        if cmd in ("sanctions", "bans"):
            target_user_id = getattr(args, "target_user_id", None)
            if not target_user_id and getattr(args, "uname", None):
                target_user_id = await resolve_user_by_name(client, args.uname)
            sanction_params: dict = {}
            if target_user_id:
                sanction_params["targetUserId"] = target_user_id
            if getattr(args, "direction", None):
                sanction_params["direction"] = args.direction
            if getattr(args, "limit", None) is not None:
                sanction_params["limit"] = args.limit
            try:
                result = await client.call_endpoint("sanction.getPaginated", sanction_params)
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── search ────────────────────────────────────────────────────────────
        if cmd == "search":
            try:
                result = await client.call_endpoint(
                    "search.searchAnything", {"searchText": args.query}
                )
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)
            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)
            if args.humanize or (out_path and fmt != "json"):
                text = humanize_search(result, args.query)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
            else:
                if out_path:
                    save_output(result, out_path)
                elif args.raw:
                    print(json.dumps(result))
                else:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── ranking ───────────────────────────────────────────────────────────
        if cmd == "ranking":
            ranking_type = args.type
            if ranking_type == "battle":
                battle_id = getattr(args, "battle_id", None)
                if not battle_id and getattr(args, "battle_url", None):
                    parsed = parse_warera_url(args.battle_url)
                    if parsed and parsed[0] == "battle":
                        battle_id = parsed[1]
                if not battle_id:
                    print(
                        "error: ranking --type battle requires --battle-id ID or --battle-url URL",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                entity = getattr(args, "entity", None)
                side = getattr(args, "side", None)
                if not entity:
                    print(
                        "error: ranking --type battle requires --entity user|country|mu",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                if not side:
                    print(
                        "error: ranking --type battle requires --side attacker|defender|merged",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                ranking_params: dict = {
                    "battleId": battle_id,
                    "type": entity,
                    "side": side,
                    "dataType": getattr(args, "data_type", "damage") or "damage",
                }
                try:
                    result = await client.call_endpoint("battleRanking.getRanking", ranking_params)
                except Exception as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Global ranking: API field is "rankingType", not "type"
                ranking_params = {"rankingType": ranking_type}
                if getattr(args, "limit", None) is not None:
                    ranking_params["limit"] = args.limit
                try:
                    result = await client.call_endpoint("ranking.getRanking", ranking_params)
                except Exception as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    sys.exit(1)
            out_path = resolve_output(args)
            if out_path:
                save_output(result, out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        # ── raw ───────────────────────────────────────────────────────────────
        if cmd == "raw":
            params = build_params(args, resolved_country_id)
            try:
                result = await client.call_endpoint(args.endpoint, params)
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            out_path = resolve_output(args)
            fmt = resolve_format(args, out_path)

            if args.humanize and args.endpoint == "event.getEventsPaginated":
                events = result.get("items", result) if isinstance(result, dict) else result
                country_map, region_map, user_map = await build_lookup_maps(
                    client, events, show_progress=args.progress
                )
                text = humanize_events(events, country_map, region_map, user_map)
                if out_path:
                    save_output(text, out_path)
                else:
                    print(text)
                return

            if out_path:
                save_output(result if fmt == "json" else json.dumps(result, indent=2, ensure_ascii=False), out_path)
            elif args.raw:
                print(json.dumps(result))
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
