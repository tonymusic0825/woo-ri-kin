import json
import logging
from collections import Counter
from pathlib import Path

import aiohttp

log = logging.getLogger(__name__)

V1 = "https://api.warframe.market/v1"
TIMEOUT = aiohttp.ClientTimeout(total=10)
HEADERS = {
    "Accept": "application/json",
    "Platform": "pc",
    "User-Agent": "warframe-discord-bot (personal project)",
}
DATA = Path(__file__).resolve().parent.parent / "data"


def _load(filename, default=None):
    path = DATA / filename
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"{path} not found. Run: python dl/warframe_market_dl.py")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- Search keys (names, initials, aliases) ----------

def _key(text):
    """Lowercase and drop spaces, so '치명타확률' matches '치명타 확률'."""
    return "".join(text.lower().split())


def _initials(name):
    """'치명타 확률' -> '치확', 'Critical Chance' -> 'cc'. Multi-word names only."""
    words = (name or "").split()
    return "".join(w[0] for w in words) if len(words) > 1 else None


def _prepare(items, aliases):
    """Give each item a set of search keys: slug, names, unique initials, manual aliases."""
    slugs = {item["slug"] for item in items}
    for slug in set(aliases) - slugs:
        log.warning("Alias file has unknown slug: %s", slug)

    # initials shared by two items are ambiguous, so skip those
    counts = Counter()
    for item in items:
        counts.update({_initials(item["name_ko"]), _initials(item["name_en"])})

    for item in items:
        keys = [item["slug"], item["name_en"], item["name_ko"], *aliases.get(item["slug"], [])]
        for abbr in (_initials(item["name_ko"]), _initials(item["name_en"])):
            if abbr and counts[abbr] == 1:
                keys.append(abbr)
        item["keys"] = {_key(k) for k in keys if k}

    return items


ALIASES = _load("riven_aliases_ko.json", default={})
WEAPONS = _prepare(_load("riven_weapons.json"), ALIASES.get("weapons", {}))
ATTRIBUTES = _prepare(_load("riven_attributes.json"), ALIASES.get("attributes", {}))


# ---------- Name lookup ----------

def _match(items, query, limit):
    """Exact key match first, then prefix, then substring."""
    q = _key(query)
    exact, starts, contains = [], [], []

    for item in items:
        keys = item["keys"]
        if q in keys:
            exact.append(item)
        elif any(k.startswith(q) for k in keys):
            starts.append(item)
        elif any(q in k for k in keys):
            contains.append(item)

    return (exact + starts + contains)[:limit]


def find_weapons(query, limit=25):
    return _match(WEAPONS, query, limit)


def find_attributes(query, limit=25):
    return _match(ATTRIBUTES, query, limit)


_ATTRIBUTE_BY_SLUG = {a["slug"]: a for a in ATTRIBUTES}


def get_attribute(slug):
    """Look up an attribute by its exact slug (e.g. from an auction). None if unknown."""
    return _ATTRIBUTE_BY_SLUG.get(slug)


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

    weapon, positives, and negative can be Korean names, English names, slugs, or aliases.
    Example: await search_rivens("브래톤", ["치확", "멀샷"], "줌")
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