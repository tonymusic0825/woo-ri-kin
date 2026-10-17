import json
import os
from datetime import datetime, timezone
import aiohttp
import time

WORLDSTATE_URL = "https://api.warframe.com/cdn/worldState.php"
TIMEOUT = aiohttp.ClientTimeout(total=10)
NODES_PATH = "data/solNodes.json"
ITEMS_PATH = "data/items.json"

TIERS = {
    "VoidT1": ("Lith", 1),
    "VoidT2": ("Meso", 2),
    "VoidT3": ("Neo", 3),
    "VoidT4": ("Axi", 4),
    "VoidT5": ("Requiem", 5),
    "VoidT6": ("Omnia", 6),
}

MISSION_TYPES = {
    "MT_EXTERMINATION": "Exterminate",
    "MT_SURVIVAL": "Survival",
    "MT_DEFENSE": "Defense",
    "MT_MOBILE_DEFENSE": "Mobile Defense",
    "MT_CAPTURE": "Capture",
    "MT_RESCUE": "Rescue",
    "MT_SABOTAGE": "Sabotage",
    "MT_INTEL": "Spy",
    "MT_TERRITORY": "Interception",
    "MT_EXCAVATE": "Excavation",
    "MT_RETRIEVAL": "Hijack",
    "MT_ASSAULT": "Assault",
    "MT_HIVE": "Hive",
    "MT_ARTIFACT": "Disruption",
    "MT_VOID_CASCADE": "Void Cascade",
    "MT_CORRUPTION": "Void Flood",
    "MT_ALCHEMY": "Alchemy",
}

FACTIONS = {
    "FC_GRINEER": "그리니어",
    "FC_CORPUS": "코퍼스",
    "FC_INFESTATION": "감염체",
    "FC_OROKIN": "오로킨",
    "FC_SENTIENT": "센티언트",
    "FC_MITW": "머머",
    "FC_TECHROT": "테크롯",
    "FC_SCALDRA": "스칼드라",
}
 
# Deviation / risk codes -> display names.
# Unknown codes print to the console; add them here as you see them, e.g.
#   "GrowingIncursion": "성장하는 침입",
ARCHIMEDEA_NAMES = {
}

def _load_json(path):
    if not os.path.exists(path):
        print(f"Warning: {path} not found. Names will show as raw codes.")
        return {}
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)
 
NODES = _load_json(NODES_PATH) 

# ---------- Translation helpers ----------

def _ms_to_iso(date_obj):
    """{"$date": {"$numberLong": "1791880389686"}} -> "2026-10-13T10:33:09.686Z" """
    ms = int(date_obj["$date"]["$numberLong"])
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

def _node_name(code):
    entry = NODES.get(code)
    if entry is None:
        print(f"Unknown node code: {code}")
        return code
    return entry["value"]

def _mission_name(code):
    name = MISSION_TYPES.get(code)
    if name is None:
        print(f"Unknown mission type code: {code}")
        return code
    return name

def _ms(date_obj):
    """{"$date": {"$numberLong": "1791880389686"}} -> 1791880389686"""
    return int(date_obj["$date"]["$numberLong"])

def _item_name(path, ITEMS):
    """NEW: "/Lotus/StoreItems/Upgrades/Mods/..." -> "Primed Continuity" (or Korean)"""
    key = path.replace("/StoreItems", "")  # item lists don't use the /StoreItems part
    entry = ITEMS.get(key)
    if entry is None:
        print(f"Unknown item: {path}")
        return path.split("/")[-1]  # fallback: last part of the path
    return entry["ko"]  # change to entry["en"] for English

# ---------- Fetching ----------

async def _get_worldstate():
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(WORLDSTATE_URL) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

def _parse_fissure(m):
    tier, tier_num = TIERS.get(m["Modifier"], (m["Modifier"], 0))
    node = _node_name(m["Node"])
    mission = _mission_name(m["MissionType"])

    # Same keys and formats warframestat used, so the cogs don't need changes
    return {
        "id": m["_id"]["$oid"],
        "node": node,
        "nodeKey": node,
        "missionType": mission,
        "missionTypeKey": mission,
        "tier": tier,
        "tierNum": tier_num,
        "isHard": m.get("Hard", False),
        "isStorm": False,
        "activation": _ms_to_iso(m["Activation"]),
        "expiry": _ms_to_iso(m["Expiry"]),
    }

async def get_fissures():
    ws = await _get_worldstate()
    fissures = []
    for m in ws.get("ActiveMissions", []):
        try:
            fissures.append(_parse_fissure(m))
        except Exception as e:
            print(f"Skipping a fissure that failed to parse: {e}")
    return fissures

async def get_baro():
    ws = await _get_worldstate()
    traders = ws.get("VoidTraders", []) 
    if not traders:
        return {"active": False}

    t = traders[0]
    now_ms = time.time() * 1000
    active = _ms(t["Activation"]) <= now_ms < _ms(t["Expiry"])
    ITEMS = _load_json(ITEMS_PATH) # This is loading items json for translation

    inventory = [
        {
            "item": _item_name(i["ItemType"], ITEMS=ITEMS),
            "ducats": i.get("PrimePrice", 0),
            "credits": i.get("RegularPrice", 0),
        }
        for i in t.get("Manifest", [])  # Manifest only exists while he's here
    ]

    return {
        "active": active,
        "activation": _ms_to_iso(t["Activation"]),
        "expiry": _ms_to_iso(t["Expiry"]),
        "location": _node_name(t["Node"]),
        "inventory": inventory,
    }

def _faction_name(code):
    name = FACTIONS.get(code)
    if name is None:
        print(f"Unknown faction code: {code}")
        return code
    return name
 
 
def _split_camel(code):
    """Fallback: "GrowingIncursion" -> "Growing Incursion" """
    out = ""
    for i, ch in enumerate(code):
        if ch.isupper() and i > 0 and code[i - 1].islower():
            out += " "
        out += ch
    return out
 
 
def _archimedea_name(code):
    name = ARCHIMEDEA_NAMES.get(code)
    if name is None:
        print(f"Unknown Archimedea code: {code}")
        return _split_camel(code)
    return name
 
 
def _parse_conquest(c):
    missions = []
    for m in c.get("Missions", []):
        # difficulties: [{"type": "CD_NORMAL", ...}, {"type": "CD_HARD", ...}]
        diffs = {d["type"]: d for d in m.get("difficulties", [])}
        normal = diffs.get("CD_NORMAL", {})
        hard = diffs.get("CD_HARD", {})
 
        normal_risks = normal.get("risks", [])
        elite_extra = [r for r in hard.get("risks", []) if r not in normal_risks]
 
        missions.append({
            "faction": _faction_name(m.get("faction", "?")),
            "missionType": _mission_name(m.get("missionType", "?")),
            "deviation": _archimedea_name(normal.get("deviation", "?")),
            "risks": [_archimedea_name(r) for r in normal_risks],
            "eliteRisks": [_archimedea_name(r) for r in elite_extra],
        })
 
    return {
        "type": c.get("Type"),  # "CT_LAB" = Deep Archimedea, "CT_HEX" = Temporal (Hex)
        "activation": _ms_to_iso(c["Activation"]),
        "expiry": _ms_to_iso(c["Expiry"]),
        "missions": missions,
    }
 
 
async def get_conquests():
    ws = await _get_worldstate()
    conquests = []
    for c in ws.get("Conquests", []):
        try:
            conquests.append(_parse_conquest(c))
        except Exception as e:
            print(f"Skipping an Archimedea that failed to parse: {e}")
    return conquests
