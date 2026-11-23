from fastapi.testclient import TestClient

from sp.core.db import get_db
from sp.main import app


class _FakeResult:
    pass


class _FakeSession:
    def __init__(self, *, fail_on: set[str] | None = None) -> None:
        self._fail_on = fail_on or set()
        self.rolled_back = False

    def execute(self, clause):
        text = str(clause)
        for needle in self._fail_on:
            if needle in text:
                raise RuntimeError("fallo simulado")
        return _FakeResult()

    def rollback(self) -> None:
        self.rolled_back = True


def _override_db(session: _FakeSession):
    def _get_db():
        yield session

    return _get_db


def test_health_ok() -> None:
    app.dependency_overrides[get_db] = _override_db(_FakeSession())
    try:
        client = TestClient(app)
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok", "queue": "ok"}


def test_health_degraded_when_queue_unreachable() -> None:
    app.dependency_overrides[get_db] = _override_db(_FakeSession(fail_on={"procrastinate_jobs"}))
    try:
        client = TestClient(app)
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "ok"
    assert body["queue"] == "error"


def test_request_id_header_is_set_and_echoed() -> None:
    app.dependency_overrides[get_db] = _override_db(_FakeSession())
    try:
        client = TestClient(app)
        response = client.get("/health", headers={"x-request-id": "abc-123"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.headers["x-request-id"] == "abc-123"
