import aiohttp

BASE_URL = "https://api.warframestat.us/pc"
TIMEOUT = aiohttp.ClientTimeout(total=10) 

async def _get(endpoint):
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(f"{BASE_URL}/{endpoint}") as resp:
            resp.raise_for_status()
            return await resp.json()

async def get_fissures():
    return await _get("fissures")

async def get_baro():
    return await _get("voidTrader")

async def get_fissures():
    return await _get("fissures")
 
 
async def get_baro():
    # Baro Ki'Teer: active, location, activation, expiry, inventory[]
    return await _get("voidTrader")
 
 
async def get_archon_hunt():
    # Weekly Archon Hunt (Archon Shards): boss, faction, missions[], expiry
    return await _get("archonHunt")
 
 
async def get_steel_path():
    # Teshin's Steel Path Honors: currentReward, rotation[], expiry
    return await _get("steelPath")
 
 
async def get_archimedeas():
    # List of weekly Archimedeas: Deep (CT_LAB) and Temporal / Hex (CT_HEX)
    return await _get("archimedeas")