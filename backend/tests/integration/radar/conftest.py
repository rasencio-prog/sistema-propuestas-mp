from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet

from sp.core import crypto
from sp.modules.organizations.models import ApiCredential, Organization
from sp.modules.scoring.models import ScoringProfile
from sp.modules.service_lines.models import ServiceLine


@pytest.fixture(autouse=True)
def _fake_encryption_key(monkeypatch: pytest.MonkeyPatch):
    """`crypto.encrypt`/`decrypt` leen `APP_ENCRYPTION_KEY` via `get_settings()` (cacheada con
    `lru_cache`): se fija una clave ficticia y se limpia el cache de `_fernet` para no depender del
    `.env` real en estas pruebas (CLAUDE.md: nunca depender de secretos reales en pruebas)."""
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    from sp.core.settings import get_settings

    get_settings.cache_clear()
    crypto._fernet.cache_clear()
    yield
    get_settings.cache_clear()
    crypto._fernet.cache_clear()


@pytest.fixture
def radar_fixture(db_session):
    """Organizacion + credencial (ticket ficticio cifrado) + scoring_profile activo + lineas de
    servicio con palabras clave TI, listas para correr `run_radar` en una prueba de integracion."""
    organization = Organization(legal_name=f"Org radar {uuid.uuid4()}")
    db_session.add(organization)
    db_session.flush()

    credential = ApiCredential(
        organization_id=organization.id,
        provider="mercado_publico",
        ticket_encrypted=crypto.encrypt("ticket-de-prueba"),
        daily_limit=8000,
        is_active=True,
    )
    db_session.add(credential)

    scoring_profile = ScoringProfile(organization_id=organization.id, version=1, is_active=True)
    db_session.add(scoring_profile)

    service_line = ServiceLine(
        organization_id=organization.id,
        name="Desarrollo de software",
        positive_keywords=["software", "aplicaciones", "sistemas web"],
        exclusion_keywords=["mobiliario"],
        category_codes=["43231500"],
    )
    db_session.add(service_line)
    db_session.flush()

    return {
        "organization": organization,
        "credential": credential,
        "scoring_profile": scoring_profile,
        "service_line": service_line,
    }
