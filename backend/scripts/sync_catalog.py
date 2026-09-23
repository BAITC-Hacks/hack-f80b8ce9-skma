"""Download the ekt.kz product list into backend/data/catalog.json.

Usage: .venv/bin/python -m scripts.sync_catalog  (or `make sync-catalog`)
"""

import asyncio
import time

from app.core.config import settings
from app.services.catalog_service import CatalogService


async def main() -> None:
    started = time.monotonic()
    count = await CatalogService().sync(max_pages=settings.ekt_sync_pages)
    print(f"Saved {count} products in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
