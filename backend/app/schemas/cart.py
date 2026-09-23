from pydantic import BaseModel


class PendingAdd(BaseModel):
    pending_id: str
    product_id: int
    article: str
    name: str
    price: float | None
    qty: int
    requested_qty: int
    max_qty: int


class CartItem(BaseModel):
    product_id: int
    article: str
    name: str
    price: float | None
    qty: int


class Cart(BaseModel):
    cart_id: str
    items: list[CartItem]
    total: float


class PendingActionRequest(BaseModel):
    pending_id: str
