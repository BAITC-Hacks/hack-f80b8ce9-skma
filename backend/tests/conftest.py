import os

# Must be set before the app is imported: tests use in-memory SQLite and no real LLM.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = ""

import copy  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from app.main import app  # noqa: E402
from app.services.assistant_service import (  # noqa: E402
    SessionStore,
    get_checkpointer,
    get_llm_client,
    get_session_store,
)
from app.services.catalog_service import CatalogService, get_catalog_service  # noqa: E402
from app.services.item_service import ItemService, get_item_service  # noqa: E402
from tests.catalog_data import DETAILS, entries  # noqa: E402


class FakeEkt:
    """ekt.kz API served from DETAILS; tests can change stock and count calls."""

    def __init__(self) -> None:
        self.details = copy.deepcopy(DETAILS)
        self.calls = 0
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.down:
            return httpx.Response(500)
        product_id = int(request.url.params.get("id", 0))
        if request.url.path.endswith("/products/detail") and product_id in self.details:
            return httpx.Response(200, json=self.details[product_id])
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def ekt() -> FakeEkt:
    return FakeEkt()


@pytest.fixture
def catalog(ekt: FakeEkt) -> CatalogService:
    return CatalogService(entries=entries(), transport=httpx.MockTransport(ekt.handler))


@pytest.fixture
def client(catalog: CatalogService) -> TestClient:
    items = ItemService()
    sessions = SessionStore()
    saver = InMemorySaver()
    app.dependency_overrides[get_item_service] = lambda: items
    app.dependency_overrides[get_catalog_service] = lambda: catalog
    app.dependency_overrides[get_session_store] = lambda: sessions
    app.dependency_overrides[get_checkpointer] = lambda: saver
    app.dependency_overrides[get_llm_client] = lambda: None
    # The context manager runs the lifespan, which creates tables in a fresh SQLite DB.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
