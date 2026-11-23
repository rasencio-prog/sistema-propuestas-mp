"""E1-6 (docs/05-backlog): matriz de permisos probada por ruta — solo_lectura no puede modificar
nada; admin si puede. Usa la app real (FastAPI) con TestClient, solo sustituyendo quien es el
usuario actual y la sesion de base (apunta al esquema `test`, nunca a `app`)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from sp.api.deps import CurrentUser, get_current_user
from sp.core.db import get_db
from sp.main import app


@pytest.fixture
def seeded_service_line(db_session) -> dict:
    org_id = db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org permisos') RETURNING id")
    ).scalar_one()
    line_id = db_session.execute(
        text(
            "INSERT INTO service_lines (organization_id, name) "
            "VALUES (:org_id, 'Linea de prueba') RETURNING id"
        ),
        {"org_id": org_id},
    ).scalar_one()
    db_session.flush()
    return {"organization_id": org_id, "service_line_id": line_id}


@pytest.fixture
def client(db_session, seeded_service_line):
    def _current_user(role: str) -> CurrentUser:
        return CurrentUser(
            user_id=uuid.uuid4(),
            email="x@example.com",
            organization_id=seeded_service_line["organization_id"],
            role=role,
        )

    def _override_db():
        yield db_session

    # TestClient simula el cliente por defecto como ("testclient", 50000); "testclient" no es una
    # IP valida para la columna `inet` de audit_events (solo pasa en pruebas: una peticion real
    # siempre trae una IP real). Se fija una IP valida para que las rutas que auditan funcionen.
    test_client = TestClient(app, client=("127.0.0.1", 123))
    test_client.seeded = seeded_service_line  # type: ignore[attr-defined]
    test_client.set_role = lambda role: app.dependency_overrides.__setitem__(  # type: ignore[attr-defined]
        get_current_user, lambda: _current_user(role)
    )
    app.dependency_overrides[get_db] = _override_db
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_read_only_can_list_service_lines(client) -> None:
    client.set_role("read_only")
    response = client.get("/api/config/service-lines")
    assert response.status_code == 200


def test_read_only_cannot_create_service_line(client) -> None:
    client.set_role("read_only")
    response = client.post("/api/config/service-lines", json={"name": "Nueva"})
    assert response.status_code == 403


def test_read_only_cannot_update_service_line(client) -> None:
    client.set_role("read_only")
    line_id = client.seeded["service_line_id"]
    response = client.patch(f"/api/config/service-lines/{line_id}", json={"is_active": False})
    assert response.status_code == 403


def test_admin_can_create_service_line(client) -> None:
    client.set_role("admin")
    response = client.post("/api/config/service-lines", json={"name": "Nueva linea admin"})
    assert response.status_code == 201
    assert response.json()["name"] == "Nueva linea admin"


def test_admin_can_update_service_line(client) -> None:
    client.set_role("admin")
    line_id = client.seeded["service_line_id"]
    response = client.patch(f"/api/config/service-lines/{line_id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
