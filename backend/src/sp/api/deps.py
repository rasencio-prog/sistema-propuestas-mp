"""Dependencias FastAPI: sesion de base, usuario actual, organizacion y rol requerido (ADR-0003)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.core.db import get_db
from sp.core.security import InvalidTokenError, decode_supabase_jwt
from sp.modules.organizations.models import OrganizationMember
from sp.modules.users.models import User

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    email: str
    organization_id: uuid.UUID
    role: str


def get_session(db: Session = Depends(get_db)) -> Generator[Session]:
    yield db


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        claims = decode_supabase_jwt(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido o expirado."
        ) from exc

    user = db.scalars(
        select(User).where(
            User.auth_user_id == uuid.UUID(claims.auth_user_id),
            User.deleted_at.is_(None),
            User.status == "active",
        )
    ).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sin cuenta activa en el sistema."
        )

    membership = db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sin membresia activa.")

    return CurrentUser(
        user_id=user.id,
        email=user.email,
        organization_id=membership.organization_id,
        role=membership.role,
    )


def require_role(*roles: str):
    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol '{current_user.role}' no autorizado para esta accion.",
            )
        return current_user

    return _check
