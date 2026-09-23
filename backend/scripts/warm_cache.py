"""Pre-load product details (and analog candidates) into the detail cache before a demo,
so answers are fast even when the ekt.kz API is slow.

Usage: .venv/bin/python -m scripts.warm_cache [article or query ...]
       (or `make warm-cache`; without arguments the demo products below are used)
"""

import asyncio
import sys
import time

from app.services.catalog_service import catalog_service
from app.services.search_service import SearchService

DEMO_QUERIES = [
    "200300285_",  # 027228 Legrand DRX250 160А: in stock
    "150100218_",  # NTV 130 E40: out of stock -> analogs
    "Автомат Legrand DRX250 160А",
    "диф автомат 16А 30мА",
    "лампа LED 10W E27",
]


async def main(queries: list[str]) -> None:
    search = SearchService(catalog_service)
    for query in queries:
        started = time.monotonic()
        entries = search.search(query, 3)
        cards = await catalog_service.get_products([e.id for e in entries], timeout=60)
        analogs = 0
        for card in cards:
            analogs += len(await search.find_analogs(card, timeout=60))
        elapsed = time.monotonic() - started
        print(f"{query!r}: {len(cards)} products, {analogs} analogs, {elapsed:.1f}s")
    await catalog_service.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or DEMO_QUERIES))
