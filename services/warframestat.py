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