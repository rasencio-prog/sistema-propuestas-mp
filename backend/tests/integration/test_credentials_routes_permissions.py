"""E1-7: solo administrador puede dar de alta/rotar el ticket; cualquier rol autenticado puede verlo
(siempre enmascarado) y la auditoria registra el cambio sin guardar el ticket en claro."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from sp.api.deps import CurrentUser, get_current_user
from sp.core.db import get_db
from sp.main import app
from sp.modules.audit.models import AuditEvent


@pytest.fixture
def seeded_organization(db_session) -> dict:
    org_id = db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org credenciales rutas') RETURNING id")
    ).scalar_one()
    db_session.flush()
    return {"organization_id": org_id}


@pytest.fixture
def client(db_session, seeded_organization):
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
    test_client.set_role = lambda role: app.dependency_overrides.__setitem__(  # type: ignore[attr-defined]
        get_current_user, lambda: _current_user(role)
    )
    app.dependency_overrides[get_db] = _override_db
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_get_credential_is_null_when_none_configured(client) -> None:
    client.set_role("read_only")
    response = client.get("/api/config/mp-credential")
    assert response.status_code == 200
    assert response.json() is None


def test_read_only_cannot_set_credential(client) -> None:
    client.set_role("read_only")
    response = client.post("/api/config/mp-credential", json={"ticket": "ticket-de-prueba-123"})
    assert response.status_code == 403


def test_admin_can_set_credential_masked_in_response(client, db_session) -> None:
    client.set_role("admin")
    response = client.post(
        "/api/config/mp-credential",
        json={"ticket": "ticket-de-prueba-secreto-1234", "holder_name": "Robinson Asencio"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_masked"] == "••••1234"
    assert "ticket-de-prueba-secreto-1234" not in response.text
    assert body["is_active"] is True

    event = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "api_credential.rotated")).one()
    assert "ticket-de-prueba-secreto-1234" not in str(event.metadata_)


def test_any_authenticated_role_can_read_masked_credential(client) -> None:
    client.set_role("admin")
    client.post("/api/config/mp-credential", json={"ticket": "otro-ticket-5678"})

    client.set_role("read_only")
    response = client.get("/api/config/mp-credential")
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_masked"] == "••••5678"
