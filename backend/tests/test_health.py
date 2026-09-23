from sqlalchemy.exc import OperationalError

from app.core.db import get_session
from app.main import app


class FakeSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def execute(self, statement):
        if self.error:
            raise self.error


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_ok(client):
    app.dependency_overrides[get_session] = lambda: FakeSession()
    response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_unavailable(client):
    error = OperationalError("SELECT 1", {}, Exception("connection refused"))
    app.dependency_overrides[get_session] = lambda: FakeSession(error)
    response = client.get("/api/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
