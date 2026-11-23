"""E2-8/E2-9: ejecucion manual del radar (solo administrador) y pantalla "Lotes y ejecuciones"."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.api.deps import CurrentUser, get_current_user, get_db, require_role
from sp.modules.audit import service as audit_service
from sp.modules.radar.models import RadarRun
from sp.modules.radar.tasks import run_radar_task

router = APIRouter(prefix="/api/radar", tags=["radar"])


class RadarRunOut(BaseModel):
    id: uuid.UUID
    radar_date: date
    trigger: str
    status: str
    requests_used: int
    listed_count: int
    new_count: int
    updated_count: int
    detailed_count: int
    errors: list[dict]
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/runs", response_model=list[RadarRunOut])
def list_radar_runs(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RadarRunOut]:
    stmt = (
        select(RadarRun)
        .where(RadarRun.organization_id == current_user.organization_id)
        .order_by(RadarRun.started_at.desc())
        .limit(50)
    )
    runs = db.scalars(stmt).all()
    return [RadarRunOut.model_validate(run) for run in runs]


@router.post("/run", status_code=202)
def trigger_radar_run(
    request: Request,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Encola el radar (worker de Procrastinate); no corre en el proceso de la API porque una
    corrida completa puede tardar ~18 minutos (ADR-0010)."""
    run_radar_task.defer(trigger="manual")
    audit_service.record_event(
        db,
        action="radar.manual_run_requested",
        entity_type="radar_run",
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"status": "encolado"}
