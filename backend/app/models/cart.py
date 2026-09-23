from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list["CartItemRow"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CartItemRow.id",
    )


class CartItemRow(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(Integer)
    article: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(500))
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    qty: Mapped[int] = mapped_column(Integer)
    cart: Mapped[CartRow] = relationship(back_populates="items")


class PendingActionRow(Base):
    """An add-to-cart the assistant proposed and the customer has not confirmed yet."""

    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(Integer)
    article: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(500))
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    qty: Mapped[int] = mapped_column(Integer)
    requested_qty: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
