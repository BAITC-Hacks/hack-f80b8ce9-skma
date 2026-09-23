import asyncio
import html
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends

from app.core.config import settings
from app.schemas.product import ProductCard

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Human labels for ekt.kz `properties` codes. Codes not listed here and not in
# SERVICE_KEYS are shown as-is.
SPEC_LABELS: dict[str, str] = {
    "OBYEM": "Тип",
    "TORGOVAYA_MARKA": "Бренд",
    "ARTIKULPOSTAVSHCHIKA": "Артикул производителя",
    "KOLICHESTVO_POLYUSOV": "Количество полюсов",
    "NOMINALNYY_TOK": "Номинальный ток",
    "NOMINALNOE_NAPRYAZHENIE": "Номинальное напряжение",
    "NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST": "Отключающая способность",
    "KHARAKTERISTIKA_SRABATYVANIYA": "Характеристика срабатывания",
    "TIP_USTANOVKI": "Тип установки",
    "TIP_USTROYSTVA": "Тип устройства",
    "VYKHODNOE_NAPRYAZHENIE_": "Выходное напряжение",
    "MOSHCHNOST_W": "Мощность, Вт",
    "TSVETOVAYA_TEMPERATURA": "Цветовая температура",
    "TIP_TSOKOLYA": "Тип цоколя",
    "FORMA_LAMPY": "Форма лампы",
    "TIP_ISTOCHNIKA": "Тип источника",
    "TIP_SVETILNIKA": "Тип светильника",
    "KATEGORIYA_SVETILNIKA": "Категория светильника",
    "TIP_RASSEIVATELYA_": "Тип рассеивателя",
    "MATERIAL_KORPUSA": "Материал корпуса",
    "TSVET_KORPUSA": "Цвет корпуса",
    "SPOSOB_MONTAZHA": "Способ монтажа",
    "OBLAST_PRIMENENIYA": "Область применения",
    "NAZNACHENIE": "Назначение",
    "KATEGORIYA": "Категория",
    "KOLICHESTVO_VVODOV_VYVODOV": "Количество вводов/выводов",
    "MATERIAL": "Материал",
    "FORMA": "Форма",
    "DOPOLNITELNAYA_ZASHCHITA": "Дополнительная защита",
    "STEPEN_ZASHCHITY": "Степень защиты",
    "TSVET": "Цвет",
    "SECHENIE": "Сечение",
    "KOLICHESTVO_ZHIL": "Количество жил",
}
SERVICE_KEYS = {
    "BRAND_PRIORITY",
    "NOVINKA",
    "SPETSPREDLOZHENIE",
    "RECOMMEND",
    "IMYAKARTINKI",
    "BLOG_POST_ID",
    "POKAZYVAT_TSENY",
    "KOLICHESTVOVREZERVE",
    "KRATNOST_MIN",
    "KRATNOST_MAKS",
    "KRATNOST_MAKS_1",
}


class CatalogUnavailableError(Exception):
    """The ekt.kz API failed and there is no cached copy to fall back to."""


@dataclass
class CatalogEntry:
    """One row of the product list: enough for search, without stock."""

    id: int
    name: str
    article: str
    price: float | None
    url: str | None
    image: str | None

    @property
    def category_path(self) -> tuple[str, ...]:
        # https://ekt.kz/catalog/<section>/<category>/[<series>/]<product>/
        if not self.url:
            return ()
        parts = [p for p in urlparse(self.url).path.split("/") if p]
        return tuple(parts[1:-1]) if parts[:1] == ["catalog"] else ()


def parse_specs(properties: dict[str, Any]) -> dict[str, str]:
    specs: dict[str, str] = {}
    for key, value in properties.items():
        if key.startswith("CML2_") or key in SERVICE_KEYS:
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        value = str(value).strip()
        if value:
            specs[SPEC_LABELS.get(key, key)] = value
    return specs


def to_card(detail: dict[str, Any]) -> ProductCard:
    properties = detail.get("properties") or {}
    stock = int(detail.get("quantity") or 0)
    entry = CatalogService._entry(detail)
    try:
        min_qty = max(1, int(properties.get("KRATNOST_MIN") or 1))
    except ValueError:
        min_qty = 1
    return ProductCard(
        id=entry.id,
        article=entry.article,
        name=entry.name,
        category="/".join(entry.category_path) or None,
        price=entry.price or None,
        stock=stock,
        in_stock=stock > 0,
        stores={s["name"]: s["quantity"] for s in detail.get("stores", []) if s.get("quantity")},
        specs=parse_specs(properties),
        min_qty=min_qty,
        certificate_url=None,
        url=entry.url,
        image=entry.image,
    )


class CatalogService:
    """Product list kept locally (for search) + fresh details from the ekt.kz API."""

    def __init__(
        self,
        entries: list[CatalogEntry] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        catalog_path: Path | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self._entries = entries
        self._transport = transport
        self._catalog_path = catalog_path or BACKEND_DIR / settings.catalog_path
        # Detail cache: memory + optional SQLite file that survives restarts, so a slow or
        # down ekt.kz API still leaves us with the last known data.
        self._details: dict[int, tuple[float, ProductCard]] = {}
        self._cache_path = cache_path
        self._cache_db: sqlite3.Connection | None = None
        self._by_id: dict[int, CatalogEntry] | None = None
        self._names: dict[int, str] | None = None
        self._http: httpx.AsyncClient | None = None

    # --- local list -------------------------------------------------------------

    @property
    def entries(self) -> list[CatalogEntry]:
        if self._entries is None:
            self._entries = self._load()
        return self._entries

    @property
    def normalized_names(self) -> dict[int, str]:
        if self._names is None:
            self._names = {e.id: e.name.lower().replace("ё", "е") for e in self.entries}
        return self._names

    def by_id(self, product_id: int) -> CatalogEntry | None:
        if self._by_id is None:
            self._by_id = {e.id: e for e in self.entries}
        return self._by_id.get(product_id)

    def _load(self) -> list[CatalogEntry]:
        path = self._catalog_path
        if not path.exists():
            # Fallback so the app works before `make sync-catalog`.
            path = BACKEND_DIR / "data/catalog_sample.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["items"] if isinstance(data, dict) else data
        return [self._entry(row) for row in rows]

    @staticmethod
    def _entry(row: dict[str, Any]) -> CatalogEntry:
        return CatalogEntry(
            id=row["id"],
            name=html.unescape(row.get("name", "")),
            article=row.get("article", ""),
            price=row.get("price"),
            url=row.get("url"),
            image=row.get("image"),
        )

    # --- ekt.kz API -------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.ekt_api_url,
            auth=(settings.ekt_api_user, settings.ekt_api_password),
            timeout=15,
            transport=self._transport,
        )

    def _disk(self) -> sqlite3.Connection | None:
        if self._cache_path is None:
            return None
        if self._cache_db is None:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_db = sqlite3.connect(self._cache_path, check_same_thread=False)
            self._cache_db.execute(
                "CREATE TABLE IF NOT EXISTS details "
                "(id INTEGER PRIMARY KEY, fetched_at REAL NOT NULL, data TEXT NOT NULL)"
            )
        return self._cache_db

    def _cached(self, product_id: int) -> tuple[float, ProductCard] | None:
        if product_id in self._details:
            return self._details[product_id]
        disk = self._disk()
        row = (
            disk
            and disk.execute(
                "SELECT fetched_at, data FROM details WHERE id = ?", (product_id,)
            ).fetchone()
        )
        if row:
            self._details[product_id] = (row[0], ProductCard.model_validate_json(row[1]))
            return self._details[product_id]
        return None

    def _store(self, card: ProductCard) -> None:
        now = time.time()
        self._details[card.id] = (now, card)
        disk = self._disk()
        if disk:
            disk.execute(
                "INSERT OR REPLACE INTO details (id, fetched_at, data) VALUES (?, ?, ?)",
                (card.id, now, card.model_dump_json()),
            )
            disk.commit()

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def sync(self, max_pages: int = 0, concurrency: int = 10) -> int:
        """Download the product list into catalog.json. max_pages=0 means all pages."""
        async with self._client() as client:

            async def page(n: int, attempts: int = 3) -> list[dict[str, Any]]:
                for attempt in range(1, attempts + 1):
                    try:
                        response = await client.get("/products", params={"page": n}, timeout=60)
                        response.raise_for_status()
                        return response.json().get("items", [])
                    except httpx.HTTPError:
                        if attempt == attempts:
                            raise
                        await asyncio.sleep(2 * attempt)
                return []

            first = await page(1)
            rows, seen = list(first), {r["id"] for r in first}
            n, done = 2, not first
            while not done and (max_pages == 0 or n <= max_pages):
                last = (
                    n + concurrency - 1 if max_pages == 0 else min(n + concurrency - 1, max_pages)
                )
                batches = await asyncio.gather(*(page(i) for i in range(n, last + 1)))
                for items in batches:
                    # Past the last page the API returns page 1 again.
                    fresh = [r for r in items if r["id"] not in seen]
                    if not fresh:
                        done = True
                        break
                    rows.extend(fresh)
                    seen.update(r["id"] for r in fresh)
                n = last + 1

        self._catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self._catalog_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self._entries = [self._entry(r) for r in rows]
        self._by_id = None
        self._names = None
        return len(rows)

    async def get_product(
        self, product_id: int, fresh: bool = False, timeout: float | None = None
    ) -> ProductCard | None:
        cached = self._cached(product_id)
        max_age = 0 if fresh else settings.detail_ttl_seconds
        if cached and time.time() - cached[0] < max_age:
            return cached[1]
        if self._http is None or self._http.is_closed:
            # One keep-alive connection pool for all detail requests (no TLS handshake each time).
            self._http = self._client()
        try:
            response = await self._http.get(
                "/products/detail",
                params={"id": product_id},
                timeout=timeout or settings.detail_timeout_seconds,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if cached:
                return cached[1]
            raise CatalogUnavailableError(str(exc)) from exc
        if not isinstance(data, dict) or "id" not in data:
            return None
        card = to_card(data)
        self._store(card)
        return card

    async def get_products(
        self, ids: list[int], concurrency: int = 8, timeout: float | None = None
    ) -> list[ProductCard]:
        """Details for several products; ones that fail or are too slow are skipped."""
        semaphore = asyncio.Semaphore(concurrency)
        errors: list[CatalogUnavailableError] = []

        async def one(product_id: int) -> ProductCard | None:
            async with semaphore:
                try:
                    return await self.get_product(product_id, timeout=timeout)
                except CatalogUnavailableError as exc:
                    errors.append(exc)
                    return None

        cards = await asyncio.gather(*(one(i) for i in ids))
        available = [c for c in cards if c is not None]
        if errors and not available:
            raise errors[0]
        return available


catalog_service = CatalogService(cache_path=BACKEND_DIR / settings.detail_cache_path)


def get_catalog_service() -> CatalogService:
    return catalog_service


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
