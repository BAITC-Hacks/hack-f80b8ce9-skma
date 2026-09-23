import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.item_service import ItemService, get_item_service


@pytest.fixture
def client() -> TestClient:
    service = ItemService()
    app.dependency_overrides[get_item_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()
