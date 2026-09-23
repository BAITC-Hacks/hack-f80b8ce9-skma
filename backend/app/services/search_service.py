import re
from typing import Annotated

from fastapi import Depends
from rapidfuzz import fuzz, process

from app.core.config import settings
from app.schemas.product import Analog, ProductCard
from app.services.catalog_service import CatalogEntry, CatalogService, CatalogServiceDep

STOP_WORDS = {
    "есть", "ли", "в", "на", "наличии", "наличие", "а", "и", "какой", "какая", "какие",
    "цена", "сколько", "стоит", "нужен", "нужна", "нужно", "нужны", "покажи", "найди",
    "товар", "артикул", "арт", "шт", "штук", "штуки", "мне", "у", "вас", "по", "для", "с",
    "добавь", "добавьте", "добавить", "положи", "беру", "корзину", "корзина", "аналог",
    "аналоги", "замена", "замену", "его", "это", "еще", "хочу", "купить", "пожалуйста",
}  # fmt: skip
# How customers say it -> how the ekt.kz catalog writes it in names.
SYNONYMS = [
    (r"\bдиф\.?\s*автомат\w*|\bдифавтомат\w*", "авдт"),
    (r"\bавтоматическ\w* выключател\w*|\bавтомат\w*", "ав"),
    (r"\bсветодиодн\w*", "led"),
]
# Specs that identify a product rather than describe it: never a reason for an analog.
NOT_COMPARABLE = {"Артикул производителя"}


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е").strip().rstrip("_")


def query_terms(query: str) -> list[str]:
    words = re.findall(r"[\w.,/-]+", normalize(query))
    terms = [w.strip(".,").rstrip("_") for w in words]
    # Short numbers are quantities ("добавь 2"), not product codes.
    return [t for t in terms if t and t not in STOP_WORDS and not (t.isdigit() and len(t) < 4)]


def expand(terms: list[str]) -> str:
    query = " ".join(terms)
    for pattern, replacement in SYNONYMS:
        query = re.sub(pattern, replacement, query)
    return query


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w+.,-]+", text))


def overlap(query_tokens: set[str], name: str) -> int:
    """How many query words occur in the name; words with digits (16а, 3х2,5) count double."""
    name_tokens = tokens(name)
    return sum(
        2 if any(c.isdigit() for c in t) else 1
        for t in query_tokens
        if t in name_tokens or any(t in n for n in name_tokens)
    )


def looks_like_code(term: str) -> bool:
    """Article or manufacturer code: "200300285", "027228", "a9d31610" (not "30ма", "drx250")."""
    return len(term) >= 5 and sum(c.isdigit() for c in term) >= 5


# Main ratings in names: current "160А", power "10W", voltage "230V", size "25мм".
RATING = re.compile(r"^\d+([.,]\d+)?(а|a|w|вт|в|v|мм|mm)$")


def name_values(name: str) -> dict[str, str]:
    """Values written in the name ("3ф", "160А", "18ka") without the leading product code:
    normalized -> as written."""
    tokens = name.split()[1:]
    return {
        normalize(t): t
        for t in tokens
        if any(c.isdigit() for c in t) and len(t) <= 8 and "(" not in t
    }


class SearchService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    def search(self, query: str, limit: int = 5) -> list[CatalogEntry]:
        entries = self.catalog.entries
        terms = query_terms(query)
        if not terms:
            return []
        found: dict[int, CatalogEntry] = {}

        # 1. Exact ekt.kz article ("200300285_" or "200300285").
        codes = [t for t in terms if looks_like_code(t)]
        for entry in entries:
            if normalize(entry.article) in codes:
                found[entry.id] = entry

        # 2. Manufacturer code inside the name ("027228 АВ DRX250 ...").
        for code in codes:
            for entry in entries:
                if len(found) >= limit:
                    break
                if code in normalize(entry.name).split():
                    found.setdefault(entry.id, entry)

        # 3. Fuzzy candidates by name, re-ranked by how many query words they contain.
        if len(found) < limit:
            query = expand(terms)
            query_tokens = tokens(query)
            names = self.catalog.normalized_names
            candidates = process.extract(
                query, names, scorer=fuzz.token_set_ratio, limit=200, score_cutoff=55
            )
            candidates.sort(
                key=lambda m: (overlap(query_tokens, m[0]), fuzz.token_sort_ratio(query, m[0])),
                reverse=True,
            )
            for _, _, product_id in candidates:
                if len(found) >= limit:
                    break
                entry = self.catalog.by_id(product_id)
                if entry:
                    found.setdefault(product_id, entry)

        return list(found.values())[:limit]

    def exact(self, query: str) -> CatalogEntry | None:
        """The one product the query names by article or manufacturer code, if any."""
        codes = [t for t in query_terms(query) if looks_like_code(t)]
        if not codes:
            return None
        by_article = [e for e in self.catalog.entries if normalize(e.article) in codes]
        if len(by_article) == 1:
            return by_article[0]
        by_name = [e for e in self.catalog.entries if set(codes) & set(normalize(e.name).split())]
        return by_name[0] if len(by_name) == 1 else None

    async def find_analogs(
        self,
        product: ProductCard,
        limit: int = 3,
        candidates: int = 12,
        timeout: float | None = None,
    ) -> list[Analog]:
        """In-stock products from the same category, ranked by matching specs."""
        origin = self.catalog.by_id(product.id)
        path = origin.category_path if origin else tuple((product.category or "").split("/"))
        pool: list[CatalogEntry] = []
        # Start with the narrowest category (series) and widen until there are candidates.
        for depth in range(len(path), 1, -1):
            prefix = path[:depth]
            pool = [
                e
                for e in self.catalog.entries
                if e.id != product.id and e.category_path[:depth] == prefix
            ]
            if len(pool) >= limit * 2:
                break
        if not pool:
            return []

        ranked = process.extract(
            normalize(product.name),
            {e.id: normalize(e.name) for e in pool},
            scorer=fuzz.token_sort_ratio,
            limit=candidates,
        )
        cards = await self.catalog.get_products(
            [product_id for _, _, product_id in ranked],
            timeout=timeout or settings.analog_timeout_seconds,
        )
        similarity = {product_id: score for _, score, product_id in ranked}

        scored: list[tuple[float, Analog]] = []
        for card in cards:
            if not card.in_stock:
                continue
            matched = [
                f"{key} {value}"
                for key, value in product.specs.items()
                if key not in NOT_COMPARABLE and card.specs.get(key) == value
            ]
            values = name_values(card.name)
            shared_keys = sorted(name_values(product.name).keys() & values.keys())
            shared = [values[k] for k in shared_keys]
            name_score = sum(20 if RATING.match(k) else 8 for k in shared_keys)
            same_series = card.category == product.category
            parts = ["та же серия" if same_series else "та же категория"]
            if shared:
                parts.append("в наименовании совпадает: " + ", ".join(shared))
            if matched:
                parts.append("характеристики: " + ", ".join(matched[:3]))
            if not shared and not matched:
                parts.append("похожее наименование")
            parts.append(f"в наличии {card.stock} шт.")
            score = (
                name_score
                + len(matched) * 10
                + similarity.get(card.id, 0) / 10
                + (5 if same_series else 0)
            )
            scored.append((score, Analog(**card.model_dump(), reason="; ".join(parts))))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [analog for _, analog in scored[:limit]]


def get_search_service(catalog: CatalogServiceDep) -> SearchService:
    return SearchService(catalog)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
