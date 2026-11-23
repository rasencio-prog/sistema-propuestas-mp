"""Scheduler del radar (ADR-0007): tarea periodica cada hora que encola el radar solo si la hora
local de Chile ya paso la ventana configurada y no hay corrida exitosa para la fecha radar de hoy.
Ejecucion manual: misma tarea, trigger="manual" (API, solo administrador).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.core import crypto
from sp.core.db import get_session_factory
from sp.core.logging import get_logger
from sp.core.timezones import chile_calendar_date, chile_now
from sp.jobs.app import app
from sp.modules.organizations.models import ApiCredential, Organization
from sp.modules.organizations.settings import get_org_setting
from sp.modules.radar.models import RadarRun
from sp.modules.radar.service import (
    DEFAULT_BACKOFF_BASE_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT_SECONDS,
    RadarRunOutcome,
    run_radar,
)
from sp.modules.scoring.models import ScoringProfile
from sp.modules.service_lines.service import list_service_lines

logger = get_logger(__name__)

DEFAULT_WINDOW_START_HOUR = 1
DEFAULT_WINDOW_END_HOUR = 5

# Unica organizacion de MVP-1 (docs/00-decisiones-propietario.md, sembrada en la migracion 0003).
# Filtrar por nombre (en vez de "la primera que aparezca") evita ambiguedad si alguna vez hay mas
# de una fila en `organizations` (p. ej. datos de otras pruebas); al habilitar multiempresa esto se
# reemplaza por el `organization_id` del llamador.
DEFAULT_ORGANIZATION_LEGAL_NAME = "Databrain SpA"


def _get_default_organization(db: Session) -> Organization | None:
    return db.scalars(
        select(Organization).where(
            Organization.legal_name == DEFAULT_ORGANIZATION_LEGAL_NAME,
            Organization.deleted_at.is_(None),
        )
    ).first()


def _get_active_credential(db: Session, organization_id: uuid.UUID) -> ApiCredential | None:
    stmt = select(ApiCredential).where(
        ApiCredential.organization_id == organization_id,
        ApiCredential.provider == "mercado_publico",
        ApiCredential.is_active,
    )
    return db.scalars(stmt).one_or_none()


def _get_active_scoring_profile(db: Session, organization_id: uuid.UUID) -> ScoringProfile | None:
    stmt = select(ScoringProfile).where(
        ScoringProfile.organization_id == organization_id, ScoringProfile.is_active
    )
    return db.scalars(stmt).one_or_none()


def run_radar_for_organization(db: Session, *, trigger: str) -> RadarRunOutcome:
    """Logica real de una corrida, inyectando la sesion (testeable sin tocar el engine singleton
    de `sp.core.db`, que en produccion resuelve `DATABASE_URL` una sola vez al importarse)."""
    organization = _get_default_organization(db)
    if organization is None:
        raise RuntimeError("No hay organizacion configurada; no se puede correr el radar.")

    credential = _get_active_credential(db, organization.id)
    if credential is None:
        raise RuntimeError(
            "No hay credencial activa de Mercado Publico (api_credentials); configurela antes "
            "de correr el radar (E1-7)."
        )

    scoring_profile = _get_active_scoring_profile(db, organization.id)
    if scoring_profile is None:
        raise RuntimeError("No hay un scoring_profile activo para la organizacion.")

    service_lines = list_service_lines(db, organization.id)
    ticket = crypto.decrypt(credential.ticket_encrypted)

    return run_radar(
        db,
        organization_id=organization.id,
        credential_id=credential.id,
        ticket=ticket,
        daily_limit=credential.daily_limit,
        scoring_profile=scoring_profile,
        service_lines=service_lines,
        trigger=trigger,
        rate_limit_seconds=get_org_setting(
            organization, "radar.rate_limit_seconds", DEFAULT_RATE_LIMIT_SECONDS
        ),
        max_retries=get_org_setting(organization, "radar.max_retries", DEFAULT_MAX_RETRIES),
        backoff_base_seconds=get_org_setting(
            organization, "radar.backoff_base_seconds", DEFAULT_BACKOFF_BASE_SECONDS
        ),
    )


def execute_radar_run(trigger: str) -> RadarRunOutcome:
    db = get_session_factory()()
    try:
        return run_radar_for_organization(db, trigger=trigger)
    finally:
        db.close()


@app.task(name="radar.run", queue="radar", lock="radar-run")
def run_radar_task(trigger: str = "scheduled") -> None:
    outcome = execute_radar_run(trigger)
    logger.info("radar_task_done", status=outcome.status, run_id=str(outcome.run_id))


def is_radar_due(db: Session, *, now_chile: datetime) -> bool:
    """ADR-0007: logica pura de la decision (inyectando la sesion y la hora de Chile, testeable
    con reloj simulado sin tocar Procrastinate ni el engine singleton)."""
    organization = _get_default_organization(db)
    if organization is None:
        return False

    window_start_hour = get_org_setting(organization, "radar.window_start_hour", DEFAULT_WINDOW_START_HOUR)
    if now_chile.hour < window_start_hour:
        return False

    today = chile_calendar_date(now_chile)
    already_succeeded = db.scalars(
        select(RadarRun).where(
            RadarRun.organization_id == organization.id,
            RadarRun.radar_date == today,
            RadarRun.status == "succeeded",
        )
    ).first()
    return already_succeeded is None


@app.periodic(cron="0 * * * *", tzinfo="America/Santiago", periodic_id="radar-hourly-tick")
@app.task(name="radar.scheduler_tick")
def radar_scheduler_tick(timestamp: int) -> None:
    """ADR-0007: corre cada hora (reloj de Chile); encola el radar solo dentro de la ventana
    configurada y si todavia no hay una corrida exitosa para la fecha radar de hoy."""
    db = get_session_factory()()
    try:
        due = is_radar_due(db, now_chile=chile_now())
    finally:
        db.close()

    if due:
        run_radar_task.defer(trigger="scheduled")
