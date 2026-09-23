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
    (r"\bдиф\w*\.?\s*автомат\w*|\bдифавтомат\w*", "авдт"),
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


# Cyrillic letters that look like Latin ones: "1Р+N" = "1P+N", "16А" = "16A".
LOOKALIKES = str.maketrans("авсеохкмтрн", "abceoxkmtph")
# Ratings in names: number + unit. Main ones (current, power, voltage) decide the analog.
RATING = re.compile(r"^(\d+(?:[.,]\d+)?)(a|w|bt|b|v|mm|ma|ka)$")
MAIN_UNITS = {"a", "w", "bt", "b", "v"}


def fold(token: str) -> str:
    return normalize(token).translate(LOOKALIKES)


def name_values(name: str) -> dict[str, str]:
    """Values written in the name ("3ф", "160А", "18ka") without the leading product code:
    folded -> as written."""
    tokens = name.split()[1:]
    return {
        fold(t): t for t in tokens if any(c.isdigit() for c in t) and len(t) <= 8 and "(" not in t
    }


def ratings(values: dict[str, str]) -> dict[str, str]:
    """unit -> folded value, e.g. {"a": "16a", "ma": "30ma"}."""
    return {m.group(2): key for key in values if (m := RATING.match(key))}


def compare_names(
    original: dict[str, str], candidate: dict[str, str]
) -> tuple[int, list[str], list[str]]:
    """How close the candidate's name values are: (score, shared values, differences).
    A different main rating (10А instead of 16А) is a strong minus."""
    shared_keys = sorted(original.keys() & candidate.keys())
    score = 0
    for key in shared_keys:
        match = RATING.match(key)
        score += (20 if match.group(2) in MAIN_UNITS else 12) if match else 8
    differences = []
    candidate_ratings = ratings(candidate)
    for unit, key in ratings(original).items():
        other = candidate_ratings.get(unit)
        if other and other != key:
            score -= 30 if unit in MAIN_UNITS else 10
            differences.append(f"{candidate[other]} вместо {original[key]}")
    return score, [candidate[k] for k in shared_keys], differences


class SearchService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    def search(self, query: str, limit: int = 5, min_score: int = 55) -> list[CatalogEntry]:
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
                query, names, scorer=fuzz.token_set_ratio, limit=200, score_cutoff=min_score
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
        name = normalize(product.name)
        ranked = process.extract(
            name, {e.id: normalize(e.name) for e in pool}, scorer=fuzz.token_sort_ratio,
            limit=candidates,
        )  # fmt: skip
        # Same product from another brand or series often sits in another catalog section:
        # add the closest names from the whole catalog too.
        in_pool = {e.id for e in pool} | {product.id}
        nearby = process.extract(
            name,
            {i: n for i, n in self.catalog.normalized_names.items() if i not in in_pool},
            scorer=fuzz.token_sort_ratio,
            limit=5,
            score_cutoff=75,
        )
        ids = [product_id for _, _, product_id in [*ranked, *nearby]]
        if not ids:
            return []
        cards = await self.catalog.get_products(
            ids,
            timeout=timeout or settings.analog_timeout_seconds,
        )
        similarity = {product_id: score for _, score, product_id in [*ranked, *nearby]}

        original_values = name_values(product.name)
        scored: list[tuple[float, Analog]] = []
        for card in cards:
            if not card.in_stock:
                continue
            matched = [
                f"{key} {value}"
                for key, value in product.specs.items()
                if key not in NOT_COMPARABLE and card.specs.get(key) == value
            ]
            name_score, shared, differences = compare_names(original_values, name_values(card.name))
            same_series = card.category == product.category
            same_category = (card.category or "").split("/")[:2] == path[:2]
            parts = [
                "та же серия"
                if same_series
                else "та же категория"
                if same_category
                else "похожий товар из другого раздела"
            ]
            if shared:
                parts.append("в наименовании совпадает: " + ", ".join(shared))
            if matched:
                parts.append("характеристики: " + ", ".join(matched[:3]))
            if not shared and not matched:
                parts.append("похожее наименование")
            if differences:
                parts.append("отличается: " + ", ".join(differences))
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
