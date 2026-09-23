from pydantic import BaseModel

# Mapping from the ekt.kz API (see tests/fixtures/):
#   list   /api/products?page=N      -> id, name, article, price, image, url (no stock, no category)
#   detail /api/products/detail?id=  -> + description, quantity (total stock),
#                                       stores[{name, quantity}], properties{CODE: value}
#   category  = second-to-last path segment of `url` (catalog/<section>/<category>/<product>/)
#   specs     = `properties` without service keys (CML2_*, NOVINKA, ...), labels in catalog_service
#   min_qty   = properties.KRATNOST_MIN
#   certificate_url: the API has no certificate field yet, so it is always None


class ProductCard(BaseModel):
    id: int
    article: str
    name: str
    category: str | None = None
    price: float | None = None
    stock: int
    in_stock: bool
    stores: dict[str, int] = {}
    specs: dict[str, str] = {}
    min_qty: int = 1
    certificate_url: str | None = None
    url: str | None = None
    image: str | None = None


class Analog(ProductCard):
    reason: str
