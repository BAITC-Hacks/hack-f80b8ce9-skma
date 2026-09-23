from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cart import PendingAdd
from app.schemas.product import Analog, ProductCard


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    cart_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    products: list[ProductCard] = []
    analogs: list[Analog] = []
    pending: PendingAdd | None = None
    cart_id: str
    cart_url: str | None = None


class SpecLine(BaseModel):
    """One row of an uploaded spec (CSV/XLSX) checked against the catalog."""

    row: int
    query: str
    requested_qty: int
    status: Literal["in_stock", "partial", "out_of_stock", "not_found"]
    product: ProductCard | None = None
    analog: Analog | None = None


class UploadResponse(ChatResponse):
    filename: str
    spec: list[SpecLine]
    skipped_rows: int = 0
