"""Fixtures de integracion: Postgres real, esquema `test` (ADR-0012, docs/07 S0).

Nunca se usa DATABASE_URL (el de la app) en estas pruebas: solo TEST_DATABASE_URL, con el rol
restringido `test_runner` (local) o el servicio Postgres efimero de CI (ver `.github/workflows/ci.yml`).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL no esta configurado: ver README (configuracion de Supabase dev, "
            "esquema 'test' y rol 'test_runner') o .github/workflows/ci.yml para el servicio de CI."
        )
    return url


@pytest.fixture(scope="session")
def integration_engine():
    engine = create_engine(_test_database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            schema = conn.execute(text("SELECT current_schema()")).scalar_one()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"No se pudo conectar a TEST_DATABASE_URL: {exc}")

    if schema != "test":
        pytest.fail(
            f"current_schema() = '{schema}', se esperaba 'test'. TEST_DATABASE_URL debe fijar "
            "options=-csearch_path=test (ADR-0012); no se ejecutan pruebas de integracion sin esto "
            "para no escribir por accidente fuera del esquema 'test'."
        )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(integration_engine) -> Iterator[Session]:
    connection = integration_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def is_superuser_connection(integration_engine) -> bool:
    """CI usa un rol superusuario en su Postgres efimero; local usa el rol restringido test_runner."""
    with integration_engine.connect() as conn:
        return bool(conn.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar())
