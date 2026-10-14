import json
from pathlib import Path

import aiohttp

V1 = "https://api.warframe.market/v1"
TIMEOUT = aiohttp.ClientTimeout(total=10)
HEADERS = {
    "Accept": "application/json",
    "Platform": "pc",
    "User-Agent": "warframe-discord-bot (personal project)",
}
DATA = Path(__file__).resolve().parent.parent / "data"


def _load(filename):
    path = DATA / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python dl/warframe_market_dl.py")
    return json.loads(path.read_text(encoding="utf-8"))


WEAPONS = _load("riven_weapons.json")
ATTRIBUTES = _load("riven_attributes.json")


# ---------- Name lookup (local JSON) ----------

def _match(items, query, limit):
    """Match on slug, English, or Korean name. Exact first, then prefix, then substring."""
    q = query.strip().lower()
    exact, starts, contains = [], [], []

    for item in items:
        names = [n.lower() for n in (item["slug"], item["name_en"], item["name_ko"]) if n]
        if q in names:
            exact.append(item)
        elif any(n.startswith(q) for n in names):
            starts.append(item)
        elif any(q in n for n in names):
            contains.append(item)

    return (exact + starts + contains)[:limit]


def find_weapons(query, limit=25):
    return _match(WEAPONS, query, limit)


def find_attributes(query, limit=25):
    return _match(ATTRIBUTES, query, limit)


def _slug(finder, query):
    """Turn user input into a single slug, or raise if nothing matches."""
    matches = finder(query, limit=1)
    if not matches:
        raise ValueError(f"No match for '{query}'")
    return matches[0]["slug"]


# ---------- Riven search (v1) ----------

async def _get(url, params=None):
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


def _auction(a):
    """Flatten a v1 auction into the fields the cog needs."""
    item = a["item"]
    return {
        "url": f"https://warframe.market/auction/{a['id']}",
        "price": a.get("buyout_price"),
        "seller": a["owner"]["ingame_name"],
        "status": a["owner"]["status"],  # "ingame", "online", "offline"
        "name": item.get("name"),
        "rerolls": item.get("re_rolls"),
        "rank": item.get("mod_rank"),
        "mastery": item.get("mastery_level"),
        "polarity": item.get("polarity"),
        "attributes": [
            {"slug": s["url_name"], "value": s["value"], "positive": s["positive"]}
            for s in item.get("attributes", [])
        ],
    }


async def search_rivens(weapon, positives=(), negative=None, limit=10):
    """
    Search riven auctions, cheapest first.

    weapon, positives, and negative can be Korean names, English names, or slugs.
    Example: await search_rivens("브래톤", ["치명타 확률", "multishot"], "zoom")
    """
    if len(positives) > 3:
        raise ValueError("A riven can have at most 3 positive stats")

    params = {
        "type": "riven",
        "weapon_url_name": _slug(find_weapons, weapon),
        "buyout_policy": "direct",  # fixed-price listings only
        "sort_by": "price_asc",
    }

    if positives:
        params["positive_stats"] = ",".join(_slug(find_attributes, p) for p in positives)
    if negative:
        params["negative_stats"] = _slug(find_attributes, negative)

    data = await _get(f"{V1}/auctions/search", params)
    return [_auction(a) for a in data["payload"]["auctions"][:limit]]