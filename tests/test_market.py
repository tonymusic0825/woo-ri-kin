import asyncio
from services.warframe_market import search_rivens
import pprint

async def main():
    rivens = await search_rivens("braton", ["critical chance", "multishot"])
    # Pretty prints the entire list with clean indentation
    pprint.pprint(rivens)

asyncio.run(main())