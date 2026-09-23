from fastapi import APIRouter

from app.api.routes import cart, catalog, chat, health, items

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
