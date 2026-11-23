from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from sp.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - un /health nunca debe propagar el detalle del error
        db_status = "error"
        db.rollback()

    queue_status = "ok"
    try:
        db.execute(text("SELECT 1 FROM procrastinate_jobs LIMIT 1"))
    except Exception:  # noqa: BLE001
        queue_status = "error"
        db.rollback()

    overall = "ok" if db_status == "ok" and queue_status == "ok" else "degraded"
    return {"status": overall, "database": db_status, "queue": queue_status}
