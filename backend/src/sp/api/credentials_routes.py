"""E1-7: alta/rotacion del ticket de Mercado Publico (solo administrador), siempre enmascarado al
mostrarlo (CLAUDE.md: nunca secretos en frontend ni logs)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from sp.api.deps import CurrentUser, get_current_user, get_db, require_role
from sp.core import crypto
from sp.modules.audit import service as audit_service
from sp.modules.organizations import credentials as credentials_service
from sp.modules.organizations.models import ApiCredential

router = APIRouter(prefix="/api/config/mp-credential", tags=["config"])


class CredentialOut(BaseModel):
    id: uuid.UUID
    provider: str
    holder_name: str | None
    ticket_masked: str
    daily_limit: int
    valid_until: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CredentialIn(BaseModel):
    ticket: str = Field(min_length=1)
    holder_name: str | None = None
    daily_limit: int = Field(default=8000, ge=1, le=10000)
    valid_until: date | None = None

    @field_validator("ticket")
    @classmethod
    def _ticket_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("El ticket no puede estar vacio.")
        return stripped


def _to_out(credential: ApiCredential) -> CredentialOut:
    ticket = crypto.decrypt(credential.ticket_encrypted)
    return CredentialOut(
        id=credential.id,
        provider=credential.provider,
        holder_name=credential.holder_name,
        ticket_masked=credentials_service.mask_ticket(ticket),
        daily_limit=credential.daily_limit,
        valid_until=credential.valid_until,
        is_active=credential.is_active,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


@router.get("", response_model=CredentialOut | None)
def get_credential(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CredentialOut | None:
    credential = credentials_service.get_active_credential(db, current_user.organization_id)
    return _to_out(credential) if credential is not None else None


@router.post("", response_model=CredentialOut)
def set_credential(
    payload: CredentialIn,
    request: Request,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> CredentialOut:
    credential = credentials_service.rotate_credential(
        db,
        organization_id=current_user.organization_id,
        ticket=payload.ticket,
        holder_name=payload.holder_name,
        daily_limit=payload.daily_limit,
        valid_until=payload.valid_until,
    )
    audit_service.record_event(
        db,
        action="api_credential.rotated",
        entity_type="api_credential",
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        entity_id=credential.id,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
        metadata={
            "provider": credential.provider,
            "holder_name": credential.holder_name,
            "daily_limit": credential.daily_limit,
            "ticket_masked": credentials_service.mask_ticket(payload.ticket),
        },
    )
    db.commit()
    return _to_out(credential)
