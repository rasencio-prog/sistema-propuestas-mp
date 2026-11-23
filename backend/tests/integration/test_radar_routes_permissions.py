"""E2-8/E2-9: solo administrador puede disparar una corrida manual; cualquier rol autenticado
puede ver la lista de corridas (pantalla "Lotes y ejecuciones")."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from sp.api import radar_routes
from sp.api.deps import CurrentUser, get_current_user
from sp.core.db import get_db
from sp.main import app
from sp.modules.radar.tasks import run_radar_task


@pytest.fixture
def seeded_organization(db_session) -> dict:
    org_id = db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org radar rutas') RETURNING id")
    ).scalar_one()
    db_session.flush()
    return {"organization_id": org_id}


@pytest.fixture
def client(db_session, seeded_organization, monkeypatch: pytest.MonkeyPatch):
    deferred: list[dict] = []

    async def _fake_defer_async(**kwargs):
        deferred.append(kwargs)

    async def _fake_clear_stalled_jobs(db) -> None:
        return None

    monkeypatch.setattr(run_radar_task, "defer_async", _fake_defer_async)
    monkeypatch.setattr(radar_routes, "clear_stalled_radar_run_jobs", _fake_clear_stalled_jobs)

    def _current_user(role: str) -> CurrentUser:
        return CurrentUser(
            user_id=uuid.uuid4(),
            email="x@example.com",
            organization_id=seeded_organization["organization_id"],
            role=role,
        )

    def _override_db():
        yield db_session

    test_client = TestClient(app, client=("127.0.0.1", 123))
    test_client.deferred = deferred  # type: ignore[attr-defined]
    test_client.set_role = lambda role: app.dependency_overrides.__setitem__(  # type: ignore[attr-defined]
        get_current_user, lambda: _current_user(role)
    )
    app.dependency_overrides[get_db] = _override_db
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_read_only_can_list_runs(client) -> None:
    client.set_role("read_only")
    response = client.get("/api/radar/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_read_only_cannot_trigger_manual_run(client) -> None:
    client.set_role("read_only")
    response = client.post("/api/radar/run")
    assert response.status_code == 403
    assert client.deferred == []


def test_admin_can_trigger_manual_run(client) -> None:
    client.set_role("admin")
    response = client.post("/api/radar/run")
    assert response.status_code == 202
    assert client.deferred == [{"trigger": "manual"}]
