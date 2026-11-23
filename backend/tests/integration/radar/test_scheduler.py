"""ADR-0007: el scheduler corre exactamente una vez por dia local, con reloj simulado, incluidos
los cambios de horario de Chile (docs/07 S1).

Usa la organizacion unica sembrada por la migracion (`Databrain SpA`, ver `tasks.
DEFAULT_ORGANIZATION_LEGAL_NAME`) en vez de `radar_fixture`: `is_radar_due` resuelve la organizacion
por nombre (bridge de un solo tenant, docs/00), asi que una organizacion con otro nombre no la
encontraria y estas pruebas no estarian probando lo mismo que corre en produccion."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from sp.modules.organizations.models import Organization
from sp.modules.radar.models import RadarRun
from sp.modules.radar.tasks import DEFAULT_ORGANIZATION_LEGAL_NAME, DEFAULT_WINDOW_START_HOUR, is_radar_due


@pytest.fixture
def seeded_organization(db_session) -> Organization:
    organization = db_session.scalars(
        select(Organization).where(Organization.legal_name == DEFAULT_ORGANIZATION_LEGAL_NAME)
    ).one_or_none()
    if organization is None:
        organization = Organization(legal_name=DEFAULT_ORGANIZATION_LEGAL_NAME)
        db_session.add(organization)
        db_session.flush()
    return organization


def _chile_dt(*args: int) -> datetime:
    return datetime(*args, tzinfo=ZoneInfo("America/Santiago"))


def test_not_due_before_configured_window(db_session, seeded_organization) -> None:
    before_window = _chile_dt(2026, 11, 20, DEFAULT_WINDOW_START_HOUR - 1, 59)
    assert is_radar_due(db_session, now_chile=before_window) is False


def test_due_once_window_starts_and_no_run_today(db_session, seeded_organization) -> None:
    in_window = _chile_dt(2026, 11, 20, DEFAULT_WINDOW_START_HOUR)
    assert is_radar_due(db_session, now_chile=in_window) is True


def test_not_due_again_after_a_succeeded_run_today(db_session, seeded_organization) -> None:
    today_run = _chile_dt(2026, 11, 20, DEFAULT_WINDOW_START_HOUR)
    db_session.add(
        RadarRun(
            organization_id=seeded_organization.id,
            radar_date=today_run.date(),
            trigger="scheduled",
            status="succeeded",
        )
    )
    db_session.flush()

    later_same_day = _chile_dt(2026, 11, 20, DEFAULT_WINDOW_START_HOUR + 2)
    assert is_radar_due(db_session, now_chile=later_same_day) is False


def test_due_again_next_day_after_a_succeeded_run(db_session, seeded_organization) -> None:
    db_session.add(
        RadarRun(
            organization_id=seeded_organization.id,
            radar_date=_chile_dt(2026, 11, 20, 1).date(),
            trigger="scheduled",
            status="succeeded",
        )
    )
    db_session.flush()

    next_day = _chile_dt(2026, 11, 21, DEFAULT_WINDOW_START_HOUR)
    assert is_radar_due(db_session, now_chile=next_day) is True


def test_partial_run_today_does_not_block_rescheduling(db_session, seeded_organization) -> None:
    today_run = _chile_dt(2026, 11, 20, DEFAULT_WINDOW_START_HOUR)
    db_session.add(
        RadarRun(
            organization_id=seeded_organization.id,
            radar_date=today_run.date(),
            trigger="scheduled",
            status="partial",
        )
    )
    db_session.flush()

    assert is_radar_due(db_session, now_chile=today_run) is True


def test_due_across_dst_fall_back_transition(db_session, seeded_organization) -> None:
    # 2026-04-12: Chile atrasa el reloj ese dia; sigue siendo el mismo dia calendario de Chile.
    in_window = _chile_dt(2026, 4, 12, DEFAULT_WINDOW_START_HOUR, 30)
    assert is_radar_due(db_session, now_chile=in_window) is True


def test_due_across_dst_spring_forward_transition(db_session, seeded_organization) -> None:
    # 2026-09-06: Chile adelanta el reloj ese dia.
    in_window = _chile_dt(2026, 9, 6, DEFAULT_WINDOW_START_HOUR, 30)
    assert is_radar_due(db_session, now_chile=in_window) is True


def test_window_start_hour_is_configurable_via_org_settings(db_session, seeded_organization) -> None:
    seeded_organization.settings = {"radar": {"window_start_hour": 3}}
    db_session.flush()

    at_default_hour = _chile_dt(2026, 11, 20, 1, 30)
    assert is_radar_due(db_session, now_chile=at_default_hour) is False

    at_configured_hour = _chile_dt(2026, 11, 20, 3)
    assert is_radar_due(db_session, now_chile=at_configured_hour) is True
