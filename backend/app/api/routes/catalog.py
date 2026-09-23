from fastapi import APIRouter, HTTPException, Query

from app.schemas.product import Analog, ProductCard
from app.services.catalog_service import CatalogServiceDep, CatalogUnavailableError
from app.services.search_service import SearchServiceDep

router = APIRouter()


async def load_product(product_id: int, catalog: CatalogServiceDep) -> ProductCard:
    try:
        product = await catalog.get_product(product_id)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Catalog API unavailable") from exc
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/search", response_model=list[ProductCard])
async def search_products(
    catalog: CatalogServiceDep,
    search: SearchServiceDep,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[ProductCard]:
    entries = search.search(q, limit)
    return await catalog.get_products([e.id for e in entries])


@router.get("/{product_id}", response_model=ProductCard)
async def get_product(product_id: int, catalog: CatalogServiceDep) -> ProductCard:
    return await load_product(product_id, catalog)


@router.get("/{product_id}/analogs", response_model=list[Analog])
async def get_analogs(
    product_id: int, catalog: CatalogServiceDep, search: SearchServiceDep
) -> list[Analog]:
    product = await load_product(product_id, catalog)
    return await search.find_analogs(product)
