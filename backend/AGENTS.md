# Backend rules (FastAPI)

## Structure
- `app/main.py` — app factory, middleware, router mount. Don't put endpoints here.
- `app/api/routes/<resource>.py` — one `APIRouter` per resource, registered in `app/api/router.py`.
- `app/schemas/<resource>.py` — Pydantic models (`XCreate`, `XUpdate`, `X`).
- `app/services/<resource>_service.py` — business logic; routes stay thin.
- `app/core/config.py` — settings via `pydantic-settings`; read env only through `settings`.

## Conventions
- All routes live under `/api` (the prefix is applied in `main.py`).
- Always declare `response_model` and explicit status codes (201 create, 204 delete).
- Raise `HTTPException` with a clear `detail` for 4xx; don't return error dicts.
- Inject services via `Annotated` aliases (`ItemServiceDep`) built on
  `Depends(get_<x>_service)` so tests can override them.
- Type hints everywhere; Python 3.10 syntax (`X | None`, `list[int]`).
- Blocking I/O (LLM calls, HTTP) → use `async def` with `httpx.AsyncClient`.

## Testing
- `pytest` + `fastapi.testclient.TestClient`, fixture `client` in `tests/conftest.py`.
- Run: `make test`. Lint: `make lint`, autofix: `make format` (ruff).
