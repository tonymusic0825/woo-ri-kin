import json
import os
from datetime import datetime, timezone
import aiohttp

WORLDSTATE_URL = "https://api.warframe.com/cdn/worldState.php"
TIMEOUT = aiohttp.ClientTimeout(total=10)
NODES_PATH = "data/solNodes.json"

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

def _load_nodes():
    if not os.path.exists(NODES_PATH):
        print(f"Warning: {NODES_PATH} not found. Node names will show as raw codes.")
        return {}
    with open(NODES_PATH, encoding="utf-8") as fp:
        return json.load(fp)

NODES = _load_nodes()  # loaded once when the bot starts

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