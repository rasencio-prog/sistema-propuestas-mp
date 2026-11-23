"""E1-7: alta/rotacion del ticket de Mercado Publico cifrado (api_credentials), siempre enmascarado
al mostrarlo, y respaldo desde MP_TICKET solo si no hay ninguna fila activa (ADR-0018)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from sp.modules.organizations import credentials as credentials_service
from sp.modules.organizations.models import ApiCredential


@pytest.fixture
def organization_id(db_session) -> object:
    org_id = db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org credenciales') RETURNING id")
    ).scalar_one()
    db_session.flush()
    return org_id


def test_mask_ticket_only_shows_last_4_chars() -> None:
    assert credentials_service.mask_ticket("ABCDEFGHIJ1234") == "••••1234"
    assert credentials_service.mask_ticket("ABCDEFGHIJ1234") != "ABCDEFGHIJ1234"


def test_rotate_credential_creates_active_row_and_encrypts_ticket(db_session, organization_id) -> None:
    credential = credentials_service.rotate_credential(
        db_session,
        organization_id=organization_id,
        ticket="ticket-real-de-prueba-0001",
        holder_name="Robinson Asencio",
        daily_limit=8000,
        valid_until=None,
    )

    assert credential.is_active is True
    assert credential.ticket_encrypted != b"ticket-real-de-prueba-0001"

    fetched = credentials_service.get_active_credential(db_session, organization_id)
    assert fetched is not None
    assert fetched.id == credential.id


def test_rotate_credential_deactivates_previous_active_row(db_session, organization_id) -> None:
    first = credentials_service.rotate_credential(
        db_session,
        organization_id=organization_id,
        ticket="ticket-viejo",
        holder_name=None,
        daily_limit=8000,
        valid_until=None,
    )
    second = credentials_service.rotate_credential(
        db_session,
        organization_id=organization_id,
        ticket="ticket-nuevo",
        holder_name=None,
        daily_limit=8000,
        valid_until=None,
    )

    db_session.refresh(first)
    assert first.is_active is False
    assert second.is_active is True

    active_rows = db_session.scalars(
        select(ApiCredential).where(
            ApiCredential.organization_id == organization_id,
            ApiCredential.provider == "mercado_publico",
            ApiCredential.is_active,
        )
    ).all()
    assert len(active_rows) == 1
    assert active_rows[0].id == second.id


def test_bootstrap_from_env_only_when_no_active_row_exists(db_session, organization_id, monkeypatch) -> None:
    from sp.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "mp_ticket", "ticket-del-env")

    bootstrapped = credentials_service.get_or_bootstrap_active_credential(db_session, organization_id)
    assert bootstrapped is not None
    assert bootstrapped.daily_limit == 8000

    # Una vez que ya hay una fila activa (p. ej. dada de alta por E1-7), no se vuelve a tocar el
    # respaldo del entorno aunque siga presente.
    credentials_service.rotate_credential(
        db_session,
        organization_id=organization_id,
        ticket="ticket-de-la-ui",
        holder_name="Admin",
        daily_limit=5000,
        valid_until=None,
    )
    still_from_ui = credentials_service.get_or_bootstrap_active_credential(db_session, organization_id)
    assert still_from_ui is not None
    assert still_from_ui.holder_name == "Admin"
    assert still_from_ui.daily_limit == 5000


def test_bootstrap_returns_none_without_active_row_or_env_ticket(
    db_session, organization_id, monkeypatch
) -> None:
    from sp.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "mp_ticket", None)

    assert credentials_service.get_or_bootstrap_active_credential(db_session, organization_id) is None
