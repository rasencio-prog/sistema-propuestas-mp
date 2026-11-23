"""RLS activado sin politicas, audit_events solo-insercion, y aislamiento del rol test_runner.

(docs/07 S2 /p3; ADR-0002, ADR-0012, ADR-0014.)
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

_APP_TABLES = [
    "organizations",
    "users",
    "organization_members",
    "api_credentials",
    "service_lines",
    "audit_events",
]


def test_current_schema_is_test(db_session) -> None:
    assert db_session.execute(text("SELECT current_schema()")).scalar_one() == "test"


@pytest.mark.parametrize("table_name", _APP_TABLES)
def test_rls_is_enabled_without_policies(db_session, table_name: str) -> None:
    row = db_session.execute(
        text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :t"),
        {"t": table_name},
    ).one()
    assert row.relrowsecurity is True, f"RLS no esta activado en {table_name}"

    policy_count = db_session.execute(
        text("SELECT count(*) FROM pg_policies WHERE tablename = :t"), {"t": table_name}
    ).scalar_one()
    assert policy_count == 0, f"{table_name} no deberia tener politicas RLS todavia"


def test_audit_events_rejects_update(db_session) -> None:
    db_session.execute(
        text(
            "INSERT INTO audit_events (actor_type, action, entity_type) "
            "VALUES ('system', 'test.insert', 'test')"
        )
    )
    db_session.flush()

    with pytest.raises(DBAPIError, match="solo insercion"):
        db_session.execute(text("UPDATE audit_events SET action = 'cambiado'"))


def test_audit_events_rejects_delete(db_session) -> None:
    db_session.execute(
        text(
            "INSERT INTO audit_events (actor_type, action, entity_type) "
            "VALUES ('system', 'test.insert', 'test')"
        )
    )
    db_session.flush()

    with pytest.raises(DBAPIError, match="solo insercion"):
        db_session.execute(text("DELETE FROM audit_events"))


@pytest.mark.parametrize("table_name", _APP_TABLES)
def test_test_runner_has_no_permission_on_app_schema(
    db_session, table_name: str, is_superuser_connection
) -> None:
    if is_superuser_connection:
        pytest.skip("Conexion con rol superusuario (CI efimero): no aplica el aislamiento de test_runner.")

    has_privilege = db_session.execute(
        text("SELECT has_table_privilege(current_user, :qualified, 'SELECT')"),
        {"qualified": f"app.{table_name}"},
    ).scalar_one()
    assert has_privilege is False, f"test_runner no deberia poder leer app.{table_name}"
