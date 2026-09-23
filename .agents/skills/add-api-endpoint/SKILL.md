---
name: add-api-endpoint
description: Add a new FastAPI resource or endpoint end-to-end (schema, service, route, test, frontend client). Use when the user asks for a new API, endpoint, CRUD resource, or backend feature.
---

# Add an API endpoint

Follow `backend/AGENTS.md`. Use the `items` resource as the reference implementation.

## Steps
1. **Schema** — `backend/app/schemas/<name>.py`: `<Name>Create` (input) and `<Name>` (output, with `id`).
2. **Service** — `backend/app/services/<name>_service.py`: class with the logic,
   a module-level instance, a `get_<name>_service()` dependency and a
   `<Name>ServiceDep = Annotated[<Name>Service, Depends(get_<name>_service)]` alias.
3. **Route** — `backend/app/api/routes/<name>.py`: thin handlers with `response_model`,
   explicit status codes, `HTTPException` for 404/400.
4. **Register** — include the router in `backend/app/api/router.py`
   with `prefix="/<names>"` and a `tags` entry.
5. **Test** — `backend/tests/test_<name>.py`: happy path + one error case,
   override the service dependency in the fixture if it holds state.
6. **Frontend client** — add types and functions to `frontend/lib/api.ts`
   mirroring the schema exactly.
7. **Verify** — `make test && make lint`. Check the endpoint in `http://localhost:8000/docs`.

## Calling an external API / LLM
- Put keys in `backend/app/core/config.py` (`Settings`) and `backend/.env.example`.
- Use `async def` handlers and `httpx.AsyncClient` with a timeout.
- In tests, mock the external call — tests must not hit the network.
