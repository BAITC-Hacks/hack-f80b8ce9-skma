"""Small test catalog in the ekt.kz API format (see fixtures/ for real samples)."""

from typing import Any

from app.services.catalog_service import CatalogEntry, CatalogService

SERIES = (
    "https://ekt.kz/catalog/nizkovoltnaya_apparatura/silovye_avtomaticheskie_vyklyuchateli/drx250"
)
LAMPS = "https://ekt.kz/catalog/svetotekhnika/lampy_svetodiodnye"


def detail(
    product_id: int, name: str, article: str, price: float, qty: int, url: str, **props: str
) -> dict[str, Any]:
    return {
        "id": product_id,
        "name": name,
        "article": article,
        "description": "",
        "price": price,
        "quantity": qty,
        "stores": [
            {"id": 13, "name": "Алматы", "quantity": qty},
            {"id": 2, "name": "Брак", "quantity": 0},
        ],
        "image": None,
        "url": f"{url}/p{product_id}/",
        "offers": [],
        "properties": {"CML2_ARTICLE": article, "NOVINKA": "Нет", "KRATNOST_MIN": "1", **props},
    }


BREAKER = {"OBYEM": "Автоматический выключатель", "KOLICHESTVO_POLYUSOV": "3"}

DETAILS: dict[int, dict[str, Any]] = {
    1: detail(1, "027228 АВ DRX250 MT 3ф 160А 18ka Legrand (1)", "200300285_", 64920, 0, SERIES,
              NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST="18кА", **BREAKER),
    2: detail(2, "027230 АВ DRX250 MT 3ф 160А 25ka Legrand (1)", "200300290_", 71000, 19, SERIES,
              NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST="25кА", **BREAKER),
    3: detail(3, "027105 АВ DRX250 MT 3ф 250А 18ka Legrand (1)", "200300280_", 80000, 13, SERIES,
              NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST="18кА", **BREAKER),
    4: detail(4, "027100 АВ DRX250 MT 3ф 125А 18ka Legrand (1)", "200300284_", 60000, 0, SERIES,
              NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST="18кА", **BREAKER),
    5: detail(5, "LED ЛАМПА A60 &quot;Standart&quot; 10W 900Lm E27 MEGALIGHT (100)", "150200716_",
              450, 120, LAMPS, TIP_TSOKOLYA="E27"),
}  # fmt: skip


def entries() -> list[CatalogEntry]:
    return [CatalogService._entry(d) for d in DETAILS.values()]
