from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant_service import AssistantServiceDep
from app.services.cart_service import CartError
from app.services.catalog_service import CatalogUnavailableError

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(data: ChatRequest, assistant: AssistantServiceDep) -> ChatResponse:
    try:
        return await assistant.reply(data)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Catalog API unavailable") from exc
    except CartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
