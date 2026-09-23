import secrets
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionDep
from app.models.cart import CartItemRow, CartRow, PendingActionRow
from app.schemas.cart import Cart, CartItem, PendingAdd
from app.schemas.product import ProductCard
from app.services.catalog_service import (
    CatalogService,
    CatalogServiceDep,
    CatalogUnavailableError,
)


class CartError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def to_pending(row: PendingActionRow, max_qty: int) -> PendingAdd:
    return PendingAdd(
        pending_id=row.id,
        product_id=row.product_id,
        article=row.article,
        name=row.name,
        price=float(row.price) if row.price is not None else None,
        qty=row.qty,
        requested_qty=row.requested_qty,
        max_qty=max_qty,
    )


def to_cart(row: CartRow) -> Cart:
    items = [
        CartItem(
            product_id=i.product_id,
            article=i.article,
            name=i.name,
            price=float(i.price) if i.price is not None else None,
            qty=i.qty,
        )
        for i in row.items
    ]
    total = sum((i.price or 0) * i.qty for i in items)
    return Cart(cart_id=row.id, items=items, total=round(total, 2))


class CartService:
    """Cart changes only through confirm(); propose() never touches cart items."""

    def __init__(self, session: AsyncSession, catalog: CatalogService) -> None:
        self.session = session
        self.catalog = catalog

    async def _row(self, cart_id: str) -> CartRow | None:
        return await self.session.get(CartRow, cart_id)

    async def ensure(self, cart_id: str | None) -> CartRow:
        """Existing cart, or a new one with a server-generated id (clients can't pick ids)."""
        if cart_id and (row := await self._row(cart_id)):
            return row
        row = CartRow(id=secrets.token_urlsafe(24), items=[])
        self.session.add(row)
        await self.session.commit()
        return row

    async def get(self, cart_id: str) -> Cart | None:
        row = await self._row(cart_id)
        return to_cart(row) if row else None

    async def propose(self, cart_id: str, product: ProductCard, qty: int) -> PendingAdd:
        if qty < 1:
            raise CartError(422, "Quantity must be at least 1")
        if product.stock <= 0:
            raise CartError(409, "Product is out of stock")
        # Only the latest proposal can be confirmed.
        await self.session.execute(
            delete(PendingActionRow).where(PendingActionRow.cart_id == cart_id)
        )
        row = PendingActionRow(
            id=secrets.token_urlsafe(16),
            cart_id=cart_id,
            product_id=product.id,
            article=product.article,
            name=product.name,
            price=product.price,
            qty=min(qty, product.stock),
            requested_qty=qty,
        )
        self.session.add(row)
        await self.session.commit()
        return to_pending(row, product.stock)

    async def latest_pending(self, cart_id: str) -> PendingActionRow | None:
        result = await self.session.execute(
            select(PendingActionRow)
            .where(PendingActionRow.cart_id == cart_id)
            .order_by(PendingActionRow.created_at.desc())
        )
        return result.scalars().first()

    async def _pending(self, cart_id: str, pending_id: str) -> PendingActionRow:
        row = await self.session.get(PendingActionRow, pending_id)
        if row is None or row.cart_id != cart_id:
            raise CartError(404, "Pending action not found")
        return row

    async def confirm(self, cart_id: str, pending_id: str) -> tuple[Cart, int]:
        """Add the pending item, re-checking stock. Returns the cart and the quantity added."""
        cart = await self._row(cart_id)
        if cart is None:
            raise CartError(404, "Cart not found")
        pending = await self._pending(cart_id, pending_id)
        try:
            product = await self.catalog.get_product(pending.product_id, fresh=True)
        except CatalogUnavailableError as exc:
            raise CartError(503, "Catalog API unavailable, try again") from exc
        stock = product.stock if product else 0

        item = next((i for i in cart.items if i.product_id == pending.product_id), None)
        in_cart = item.qty if item else 0
        added = min(pending.qty, stock - in_cart)
        await self.session.delete(pending)
        if added <= 0:
            await self.session.commit()
            raise CartError(409, "Not enough stock")
        if item:
            item.qty += added
        else:
            cart.items.append(
                CartItemRow(
                    product_id=pending.product_id,
                    article=pending.article,
                    name=pending.name,
                    price=product.price if product else pending.price,
                    qty=added,
                )
            )
        await self.session.commit()
        await self.session.refresh(cart, ["items"])
        return to_cart(cart), added

    async def reject(self, cart_id: str, pending_id: str) -> None:
        pending = await self._pending(cart_id, pending_id)
        await self.session.delete(pending)
        await self.session.commit()


def get_cart_service(session: SessionDep, catalog: CatalogServiceDep) -> CartService:
    return CartService(session, catalog)


CartServiceDep = Annotated[CartService, Depends(get_cart_service)]
