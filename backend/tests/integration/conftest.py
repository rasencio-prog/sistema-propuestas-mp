"""Fixtures de integracion: Postgres real, esquema `test` (ADR-0012, docs/07 S0).

Nunca se usa DATABASE_URL (el de la app) en estas pruebas: solo TEST_DATABASE_URL, con el rol
restringido `test_runner` (local) o el servicio Postgres efimero de CI (ver `.github/workflows/ci.yml`).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from sp.core.db import attach_search_path, extract_target_schema
from sp.core.settings import get_settings

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]


def make_alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def _test_database_url() -> str:
    # get_settings().test_database_url (no os.environ directo): asi se lee igual desde .env en
    # local que desde la variable de entorno real que fija el workflow de CI.
    url = get_settings().test_database_url
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL no esta configurado: ver README (configuracion de Supabase dev, "
            "esquema 'test' y rol 'test_runner') o .github/workflows/ci.yml para el servicio de CI."
        )
    return url


@pytest.fixture(scope="session")
def integration_engine():
    url = _test_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    # El Session Pooler de Supabase ignora el parametro de arranque "options" (PgBouncer): hace
    # falta un SET search_path explicito tras conectar (ver sp.core.db, ADR-0014).
    attach_search_path(engine, extract_target_schema(url, default="test"))
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


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_schema(integration_engine) -> None:
    """Corre "alembic upgrade head" contra el esquema `test` una vez por sesion de pruebas, antes de
    cualquier otro test de integracion (pytest no garantiza el orden entre archivos: sin esto, los
    tests que no son de migraciones pueden correr primero y fallar con "relation ... does not
    exist", visto en la practica)."""
    os.environ["DATABASE_URL"] = _test_database_url()
    get_settings.cache_clear()
    try:
        command.upgrade(make_alembic_config(), "head")
    finally:
        get_settings.cache_clear()


@pytest.fixture
def db_session(integration_engine) -> Iterator[Session]:
    connection = integration_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        # Una prueba que ejercita una ruta real (p. ej. test_config_routes_permissions.py) puede
        # llamar session.commit(), lo que confirma esta misma transaccion externa; el rollback que
        # sigue entonces no tiene nada que deshacer (ya quedo inactiva) y no debe hacer fallar el
        # teardown de otras pruebas que si confian en el rollback para no dejar datos.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def is_superuser_connection(integration_engine) -> bool:
    """CI usa un rol superusuario en su Postgres efimero; local usa el rol restringido test_runner."""
    with integration_engine.connect() as conn:
        return bool(conn.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar())
