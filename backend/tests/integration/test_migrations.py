"""Alembic upgrade/downgrade contra el esquema `test` (docs/07 S2 /p3).

Las migraciones vendidas de Procrastinate son deliberadamente irreversibles (`migrations_utils.
irreversible()`); el downgrade que probamos aqui es el de nuestras 3 migraciones propias
(0001..0003), hasta volver a "procrastinate_0043".
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from sp.core.settings import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch, integration_engine) -> Config:
    # Reusa TEST_DATABASE_URL tal cual (nunca reconstruir desde engine.url: SQLAlchemy enmascara
    # la contrasena en su repr/str por seguridad, lo que rompe la reconexion).
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    get_settings.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    yield cfg
    get_settings.cache_clear()


def test_upgrade_head_then_downgrade_own_migrations(alembic_config: Config, integration_engine) -> None:
    command.upgrade(alembic_config, "head")

    inspector = inspect(integration_engine)
    tables = set(inspector.get_table_names())
    for expected in (
        "organizations",
        "users",
        "organization_members",
        "api_credentials",
        "service_lines",
        "audit_events",
        "procrastinate_jobs",
    ):
        assert expected in tables, f"falta la tabla {expected} tras 'alembic upgrade head'"

    with integration_engine.connect() as conn:
        org_count = conn.execute(text("SELECT count(*) FROM organizations")).scalar_one()
        line_count = conn.execute(text("SELECT count(*) FROM service_lines")).scalar_one()
    assert org_count >= 1
    assert line_count == 5

    command.downgrade(alembic_config, "procrastinate_0043")

    inspector = inspect(integration_engine)
    tables_after_downgrade = set(inspector.get_table_names())
    assert "organizations" not in tables_after_downgrade
    assert "audit_events" not in tables_after_downgrade
    assert "procrastinate_jobs" in tables_after_downgrade  # intacto: no es parte de nuestro downgrade

    # Deja el esquema en head para el resto de la suite de integracion.
    command.upgrade(alembic_config, "head")
