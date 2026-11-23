from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from sp.api.deps import CurrentUser, get_current_user, get_db
from sp.modules.audit import service as audit_service

router = APIRouter(prefix="/api", tags=["auth"])


def _profile(current_user: CurrentUser) -> dict:
    return {
        "user_id": str(current_user.user_id),
        "email": current_user.email,
        "organization_id": str(current_user.organization_id),
        "role": current_user.role,
    }


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    """Perfil del usuario autenticado, sin efectos secundarios (usado al cargar la app)."""
    return _profile(current_user)


@router.post("/auth/login")
def login(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Registra el evento de login en la auditoria. El frontend lo llama una vez tras iniciar sesion."""
    audit_service.record_event(
        db,
        action="login",
        entity_type="user",
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        entity_id=current_user.user_id,
        request_id=request.headers.get("x-request-id"),
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _profile(current_user)
