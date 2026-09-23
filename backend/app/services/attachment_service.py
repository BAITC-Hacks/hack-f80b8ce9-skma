"""Customer spec files (CSV / XLSX / DOCX): parse rows and check them against the catalog."""

import csv
import io
import re
from dataclasses import dataclass
from typing import Annotated

from docx import Document
from fastapi import Depends
from openpyxl import load_workbook

from app.schemas.chat import SpecLine
from app.schemas.product import Analog, ProductCard
from app.services.catalog_service import CatalogServiceDep, CatalogUnavailableError
from app.services.search_service import SearchService, SearchServiceDep

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 50
ANALOG_LOOKUPS = 10  # analogs are slow (several detail requests each)
MIN_NAME_SCORE = 70
HEADER_SEARCH_ROWS = 5  # stricter than chat search: a wrong match in a spec is worse than none

HEADERS = {
    "article": ("артикул", "арт", "код", "article", "sku", "code", "part"),
    "name": ("наименование", "название", "товар", "описание", "name", "product", "item"),
    "qty": ("кол", "количество", "кол-во", "qty", "quantity", "шт", "count", "саны"),
}


class SpecFileError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class SpecRow:
    row: int
    article: str
    name: str
    qty: int

    @property
    def query(self) -> str:
        return " ".join(p for p in (self.article, self.name) if p)


def read_table(filename: str, data: bytes) -> list[list[str]]:
    if not data:
        raise SpecFileError(422, "File is empty")
    if len(data) > MAX_FILE_BYTES:
        raise SpecFileError(413, "File is larger than 2 MB")
    name = filename.lower()
    if name.endswith(".csv"):
        return read_csv(data)
    if name.endswith(".xlsx"):
        return read_xlsx(data)
    if name.endswith(".docx"):
        return read_docx(data)
    if name.endswith(".doc"):
        raise SpecFileError(415, "Old .doc format is not supported: save the file as .docx")
    raise SpecFileError(415, "Only .csv, .xlsx and .docx files are supported")


def read_csv(data: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SpecFileError(422, "Cannot read CSV: unknown encoding")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), dialect)]


def read_xlsx(data: bytes) -> list[list[str]]:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many types for broken files
        raise SpecFileError(422, "Cannot read XLSX file") from exc
    sheet = workbook.worksheets[0]
    rows = []
    for values in sheet.iter_rows(values_only=True):
        rows.append(["" if v is None else _cell(v) for v in values])
    workbook.close()
    return rows


def read_docx(data: bytes) -> list[list[str]]:
    """A spec in Word is usually a table: take the first table with an article/name header
    (company details tables are skipped). Without tables: text lines split by tab, ";", "|"."""
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises many types for broken files
        raise SpecFileError(422, "Cannot read DOCX file") from exc
    # Merged cells repeat their text in each column, which keeps columns aligned.
    tables = [[[c.text.strip() for c in row.cells] for row in t.rows] for t in document.tables]
    for table in tables:
        if any(
            find_columns(row).keys() & {"article", "name"} for row in table[:HEADER_SEARCH_ROWS]
        ):
            return table
    if tables:
        return [row for table in tables for row in table]
    return [
        [part.strip() for part in re.split(r"\t|;|\|", p.text)]
        for p in document.paragraphs
        if p.text.strip()
    ]


def _cell(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_qty(value: str) -> int | None:
    match = re.search(r"\d+", value.replace(" ", ""))
    return int(match.group()) if match else None


def find_columns(header: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        text = cell.lower()
        for key, words in HEADERS.items():
            if key not in columns and any(text.startswith(w) or text == w for w in words):
                columns[key] = index
                break
    return columns


def parse_spec(filename: str, data: bytes) -> tuple[list[SpecRow], int]:
    """Rows with an article or name. Returns (rows, skipped rows beyond MAX_ROWS).
    Row numbers are the file's own (1-based), so the customer can find them."""
    table = [
        (number, row)
        for number, row in enumerate(read_table(filename, data), start=1)
        if any(cell for cell in row)
    ]
    if not table:
        raise SpecFileError(422, "No rows found in the file")

    # Header may sit below a title ("Спецификация к заказу ..."): look in the first rows.
    header_at = next(
        (i for i, (_, row) in enumerate(table[:HEADER_SEARCH_ROWS])
         if find_columns(row).keys() & {"article", "name"}),
        None,
    )  # fmt: skip
    if header_at is not None:
        columns = find_columns(table[header_at][1])
        body = table[header_at + 1 :]
    else:
        # No header: first text column is the product, first numeric column the quantity.
        body = table
        columns = {"name": 0}
        for index, cell in enumerate(table[0][1][1:], start=1):
            if parse_qty(cell) is not None and len(cell) <= 6:
                columns["qty"] = index
                break

    def cell(row: list[str], key: str) -> str:
        index = columns.get(key)
        return row[index].strip() if index is not None and index < len(row) else ""

    rows = []
    for number, raw in body:
        article, name = cell(raw, "article"), cell(raw, "name")
        if not article and not name:
            continue
        qty = parse_qty(cell(raw, "qty")) or 1
        rows.append(SpecRow(row=number, article=article, name=name, qty=qty))
    if not rows:
        raise SpecFileError(422, "No product rows found: add an article or name column")
    return rows[:MAX_ROWS], max(0, len(rows) - MAX_ROWS)


class SpecService:
    def __init__(self, catalog: CatalogServiceDep, search: SearchService) -> None:
        self.catalog = catalog
        self.search = search

    def _match(self, row: SpecRow) -> int | None:
        for text in (row.article, row.name):
            if text and (entry := self.search.exact(text)):
                return entry.id
        entries = self.search.search(row.query, 1, min_score=MIN_NAME_SCORE)
        return entries[0].id if entries else None

    async def check(self, rows: list[SpecRow]) -> list[SpecLine]:
        matches = {row.row: self._match(row) for row in rows}
        ids = [i for i in matches.values() if i is not None]
        cards: dict[int, ProductCard] = {c.id: c for c in await self.catalog.get_products(ids)}
        if ids and not cards:
            raise CatalogUnavailableError("no product details available")

        lines: list[SpecLine] = []
        analog_budget = ANALOG_LOOKUPS
        for row in rows:
            product_id = matches[row.row]
            card = cards.get(product_id) if product_id is not None else None
            analog: Analog | None = None
            if card is None:
                status = "not_found"
            elif card.stock >= row.qty:
                status = "in_stock"
            elif card.stock > 0:
                status = "partial"
            else:
                status = "out_of_stock"
                if analog_budget > 0:
                    analog_budget -= 1
                    found = await self.search.find_analogs(card, limit=1)
                    analog = found[0] if found else None
            lines.append(
                SpecLine(
                    row=row.row,
                    query=row.query,
                    requested_qty=row.qty,
                    status=status,
                    product=card,
                    analog=analog,
                )
            )
        return lines


def summarize(filename: str, lines: list[SpecLine], skipped: int) -> str:
    count = {s: sum(1 for x in lines if x.status == s) for s in
             ("in_stock", "partial", "out_of_stock", "not_found")}  # fmt: skip
    with_analog = sum(1 for x in lines if x.analog)
    total = sum(
        (x.product.price or 0) * min(x.requested_qty, x.product.stock)
        for x in lines
        if x.product and x.status in ("in_stock", "partial")
    )
    parts = [f"Проверил «{filename}»: {len(lines)} позиций."]
    parts.append(f"В наличии полностью: {count['in_stock']}")
    if count["partial"]:
        parts.append(f"частично: {count['partial']}")
    if count["out_of_stock"]:
        parts.append(f"нет в наличии: {count['out_of_stock']} (аналог найден для {with_analog})")
    if count["not_found"]:
        parts.append(f"не найдено в каталоге: {count['not_found']}")
    text = parts[0] + " " + ", ".join(parts[1:]) + "."
    if total:
        text += f" Сумма доступного количества: {total:,.0f} ₸.".replace(",", " ")
    if skipped:
        text += f" Обработаны первые {MAX_ROWS} строк, пропущено: {skipped}."
    return text + " Чтобы добавить позицию в корзину, напишите, например: «добавь 5 шт <артикул>»."


def spec_context(filename: str, lines: list[SpecLine]) -> str:
    """Compact description of the checked spec for the LLM's next turns."""
    rows = [
        f"стр.{x.row}: «{x.query}» ×{x.requested_qty} → "
        + (
            f"product_id={x.product.id} {x.product.article}, остаток {x.product.stock}, {x.status}"
            if x.product
            else "не найдено"
        )
        + (f"; аналог product_id={x.analog.id}" if x.analog else "")
        for x in lines
    ]
    return f"\n\nКлиент загрузил спецификацию «{filename}»:\n" + "\n".join(rows)


def get_spec_service(catalog: CatalogServiceDep, search: SearchServiceDep) -> SpecService:
    return SpecService(catalog, search)


SpecServiceDep = Annotated[SpecService, Depends(get_spec_service)]
