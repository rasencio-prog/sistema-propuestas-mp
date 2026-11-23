from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.modules.service_lines.models import ServiceLine


def list_service_lines(db: Session, organization_id: uuid.UUID) -> list[ServiceLine]:
    stmt = (
        select(ServiceLine)
        .where(ServiceLine.organization_id == organization_id, ServiceLine.deleted_at.is_(None))
        .order_by(ServiceLine.name)
    )
    return list(db.scalars(stmt))


def create_service_line(
    db: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    description: str | None,
    positive_keywords: list[str],
    exclusion_keywords: list[str],
    category_codes: list[str],
) -> ServiceLine:
    service_line = ServiceLine(
        organization_id=organization_id,
        name=name,
        description=description,
        positive_keywords=positive_keywords,
        exclusion_keywords=exclusion_keywords,
        category_codes=category_codes,
    )
    db.add(service_line)
    db.flush()
    return service_line


def update_service_line(
    db: Session,
    *,
    organization_id: uuid.UUID,
    service_line_id: uuid.UUID,
    name: str | None = None,
    description: str | None = None,
    positive_keywords: list[str] | None = None,
    exclusion_keywords: list[str] | None = None,
    category_codes: list[str] | None = None,
    is_active: bool | None = None,
) -> ServiceLine | None:
    stmt = select(ServiceLine).where(
        ServiceLine.id == service_line_id,
        ServiceLine.organization_id == organization_id,
        ServiceLine.deleted_at.is_(None),
    )
    service_line = db.scalars(stmt).one_or_none()
    if service_line is None:
        return None

    if name is not None:
        service_line.name = name
    if description is not None:
        service_line.description = description
    if positive_keywords is not None:
        service_line.positive_keywords = positive_keywords
    if exclusion_keywords is not None:
        service_line.exclusion_keywords = exclusion_keywords
    if category_codes is not None:
        service_line.category_codes = category_codes
    if is_active is not None:
        service_line.is_active = is_active

    db.flush()
    return service_line
