from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sp.api.deps import CurrentUser, get_current_user, get_db, require_role
from sp.modules.audit import service as audit_service
from sp.modules.service_lines import service as service_lines_service
from sp.modules.service_lines.models import ServiceLine

router = APIRouter(prefix="/api/config/service-lines", tags=["config"])


class ServiceLineOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    positive_keywords: list[str]
    exclusion_keywords: list[str]
    category_codes: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class ServiceLineCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    positive_keywords: list[str] = Field(default_factory=list)
    exclusion_keywords: list[str] = Field(default_factory=list)
    category_codes: list[str] = Field(default_factory=list)


class ServiceLineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    positive_keywords: list[str] | None = None
    exclusion_keywords: list[str] | None = None
    category_codes: list[str] | None = None
    is_active: bool | None = None


def _to_out(service_line: ServiceLine) -> ServiceLineOut:
    return ServiceLineOut.model_validate(service_line)


@router.get("", response_model=list[ServiceLineOut])
def list_service_lines(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ServiceLineOut]:
    lines = service_lines_service.list_service_lines(db, current_user.organization_id)
    return [_to_out(line) for line in lines]


@router.post("", response_model=ServiceLineOut, status_code=status.HTTP_201_CREATED)
def create_service_line(
    payload: ServiceLineCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ServiceLineOut:
    line = service_lines_service.create_service_line(
        db,
        organization_id=current_user.organization_id,
        name=payload.name,
        description=payload.description,
        positive_keywords=payload.positive_keywords,
        exclusion_keywords=payload.exclusion_keywords,
        category_codes=payload.category_codes,
    )
    audit_service.record_event(
        db,
        action="service_line.created",
        entity_type="service_line",
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        entity_id=line.id,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
        metadata={"name": line.name},
    )
    db.commit()
    return _to_out(line)


@router.patch("/{service_line_id}", response_model=ServiceLineOut)
def update_service_line(
    service_line_id: uuid.UUID,
    payload: ServiceLineUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ServiceLineOut:
    line = service_lines_service.update_service_line(
        db,
        organization_id=current_user.organization_id,
        service_line_id=service_line_id,
        name=payload.name,
        description=payload.description,
        positive_keywords=payload.positive_keywords,
        exclusion_keywords=payload.exclusion_keywords,
        category_codes=payload.category_codes,
        is_active=payload.is_active,
    )
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linea de servicio no encontrada.")

    audit_service.record_event(
        db,
        action="service_line.updated",
        entity_type="service_line",
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        entity_id=line.id,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
        metadata=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    return _to_out(line)
