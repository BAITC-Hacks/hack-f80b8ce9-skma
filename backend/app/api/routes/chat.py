from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.chat import ChatRequest, ChatResponse, UploadResponse
from app.services.assistant_service import AssistantServiceDep
from app.services.attachment_service import (
    MAX_FILE_BYTES,
    SpecFileError,
    SpecServiceDep,
    parse_spec,
)
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


@router.post("/upload", response_model=UploadResponse)
async def upload_spec(
    assistant: AssistantServiceDep,
    specs: SpecServiceDep,
    file: Annotated[UploadFile, File(description="Спецификация .csv или .xlsx, до 2 МБ")],
    session_id: Annotated[str, Form(min_length=1, max_length=100)],
    cart_id: Annotated[str | None, Form()] = None,
) -> UploadResponse:
    """Check a customer spec (article / name / quantity columns) against the catalog."""
    filename = file.filename or "file"
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        rows, skipped = parse_spec(filename, data)
        lines = await specs.check(rows)
    except SpecFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Catalog API unavailable") from exc
    return await assistant.attach(session_id, cart_id, filename, lines, skipped)
