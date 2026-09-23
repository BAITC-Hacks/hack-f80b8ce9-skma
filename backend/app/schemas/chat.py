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
