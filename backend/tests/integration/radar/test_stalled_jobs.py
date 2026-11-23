"""ADR-0008 (sin servidor dedicado): si el equipo del propietario se apaga a mitad de una corrida,
el job `radar.run` queda `doing` para siempre y su lock bloquearia cualquier corrida nueva. Antes de
encolar, se limpian los jobs sin heartbeat reciente y se marcan `failed` las filas `radar_runs` que
quedaron `running` para siempre (ADR-0010 addendum 2, /p4-radar segunda revision).

No abre el conector real de Procrastinate (su `conninfo` se fija al importar `sp.jobs.app`, antes de
que las fixtures de este archivo fijen `TEST_DATABASE_URL`): se mockean `get_stalled_jobs` y
`finish_job_by_id_async` directamente sobre `app.job_manager`, dejando que solo la parte sincrona
(SQLAlchemy, perezosa via `get_session_factory`) toque la base de pruebas real."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text

from sp.jobs.app import app
from sp.modules.radar.models import RadarRun
from sp.modules.radar.tasks import clear_stalled_radar_run_jobs


@dataclass
class _FakeStalledJob:
    id: int


def _seeded_organization_id(db_session) -> uuid.UUID:
    return db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org stalled jobs') RETURNING id")
    ).scalar_one()


def test_no_stalled_jobs_leaves_running_rows_untouched(db_session, monkeypatch) -> None:
    organization_id = _seeded_organization_id(db_session)
    run = RadarRun(
        organization_id=organization_id, radar_date="2026-11-23", trigger="manual", status="running"
    )
    db_session.add(run)
    db_session.flush()

    async def _fake_get_stalled_jobs(**_kwargs):
        return []

    monkeypatch.setattr(app.job_manager, "get_stalled_jobs", _fake_get_stalled_jobs)

    asyncio.run(clear_stalled_radar_run_jobs(db_session))

    db_session.refresh(run)
    assert run.status == "running"


def test_stalled_job_clears_lock_and_marks_running_rows_failed(db_session, monkeypatch) -> None:
    organization_id = _seeded_organization_id(db_session)
    stuck_run = RadarRun(
        organization_id=organization_id, radar_date="2026-11-23", trigger="manual", status="running"
    )
    other_run = RadarRun(
        organization_id=organization_id, radar_date="2026-11-22", trigger="scheduled", status="succeeded"
    )
    db_session.add_all([stuck_run, other_run])
    db_session.flush()

    finished: list[dict] = []

    async def _fake_get_stalled_jobs(**_kwargs):
        return [_FakeStalledJob(id=999)]

    async def _fake_finish_job_by_id_async(**kwargs):
        finished.append(kwargs)

    monkeypatch.setattr(app.job_manager, "get_stalled_jobs", _fake_get_stalled_jobs)
    monkeypatch.setattr(app.job_manager, "finish_job_by_id_async", _fake_finish_job_by_id_async)

    asyncio.run(clear_stalled_radar_run_jobs(db_session))

    assert finished == [{"job_id": 999, "status": finished[0]["status"], "delete_job": False}]
    assert str(finished[0]["status"]) in ("Status.FAILED", "failed")

    db_session.refresh(stuck_run)
    assert stuck_run.status == "failed"
    assert stuck_run.errors == [{"stage": "run", "error": "corrida_interrumpida_equipo_apagado"}]
    assert stuck_run.finished_at is not None

    # Una corrida ya terminada (succeeded) no se toca: solo las que quedaron 'running'.
    db_session.refresh(other_run)
    assert other_run.status == "succeeded"

    all_runs = db_session.scalars(select(RadarRun).where(RadarRun.organization_id == organization_id)).all()
    assert all(r.status != "running" for r in all_runs)
