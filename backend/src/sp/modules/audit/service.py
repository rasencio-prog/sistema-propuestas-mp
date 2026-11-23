"""Registro de auditoria reutilizable (CLAUDE.md: usado desde ya en login y cambios de configuracion).

Tabla de solo insercion (`docs/03` S3): nunca se actualiza ni se borra un `AuditEvent` ya escrito.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from sp.modules.audit.models import AuditEvent


def record_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    actor_type: str = "user",
    organization_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        user_id=user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        ip=ip,
        metadata_=metadata or {},
    )
    db.add(event)
    db.flush()
    return event
