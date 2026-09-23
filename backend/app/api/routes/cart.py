from fastapi import APIRouter, HTTPException, status

from app.schemas.cart import Cart, PendingActionRequest
from app.services.cart_service import CartError, CartServiceDep

router = APIRouter()


@router.get("/{cart_id}", response_model=Cart)
async def get_cart(cart_id: str, carts: CartServiceDep) -> Cart:
    cart = await carts.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


@router.post("/{cart_id}/confirm", response_model=Cart)
async def confirm_add(cart_id: str, data: PendingActionRequest, carts: CartServiceDep) -> Cart:
    try:
        cart, _ = await carts.confirm(cart_id, data.pending_id)
    except CartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return cart


@router.post("/{cart_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_add(cart_id: str, data: PendingActionRequest, carts: CartServiceDep) -> None:
    try:
        await carts.reject(cart_id, data.pending_id)
    except CartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
