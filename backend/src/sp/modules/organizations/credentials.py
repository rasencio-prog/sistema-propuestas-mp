"""Credencial de la API de Mercado Publico (E1-7, ADR-0018): alta/rotacion cifrada (Fernet), nunca
en texto plano fuera de memoria (CLAUDE.md: nunca secretos en codigo, logs ni frontend).

El ticket nunca se expone completo: `mask_ticket` solo deja ver los ultimos 4 caracteres.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.core import crypto
from sp.core.logging import get_logger
from sp.core.settings import get_settings
from sp.modules.organizations.models import ApiCredential

logger = get_logger(__name__)

PROVIDER = "mercado_publico"
_MASK_PREFIX = "••••"


def mask_ticket(ticket: str) -> str:
    if len(ticket) <= 4:
        return _MASK_PREFIX
    return _MASK_PREFIX + ticket[-4:]


def get_active_credential(db: Session, organization_id: uuid.UUID) -> ApiCredential | None:
    stmt = select(ApiCredential).where(
        ApiCredential.organization_id == organization_id,
        ApiCredential.provider == PROVIDER,
        ApiCredential.is_active,
    )
    return db.scalars(stmt).one_or_none()


def get_or_bootstrap_active_credential(db: Session, organization_id: uuid.UUID) -> ApiCredential | None:
    """E1-7 reemplaza el alta/rotacion manual para casos nuevos (ADR-0018), pero `MP_TICKET` (.env)
    sigue sirviendo de respaldo si todavia no hay ninguna fila activa en la base (p. ej. un entorno
    nuevo que todavia no paso por este endpoint): se crea la fila desde el entorno, con aviso en el
    log, nunca silencioso."""
    existing = get_active_credential(db, organization_id)
    if existing is not None:
        return existing

    settings = get_settings()
    if not settings.mp_ticket:
        return None

    logger.warning(
        "api_credential_bootstrapped_from_env",
        organization_id=str(organization_id),
        reason="no_hay_credencial_activa_en_la_base_se_usa_MP_TICKET_del_entorno",
    )
    credential = ApiCredential(
        organization_id=organization_id,
        provider=PROVIDER,
        ticket_encrypted=crypto.encrypt(settings.mp_ticket),
        daily_limit=8000,
        is_active=True,
    )
    db.add(credential)
    db.flush()
    return credential


def rotate_credential(
    db: Session,
    *,
    organization_id: uuid.UUID,
    ticket: str,
    holder_name: str | None,
    daily_limit: int,
    valid_until: date | None,
) -> ApiCredential:
    """Da de alta o reemplaza el ticket activo (E1-7): desactiva cualquier fila activa previa antes
    de insertar la nueva (el indice unico parcial de `api_credentials` exige una sola activa por
    organizacion/proveedor), para no perder el historial de credenciales anteriores."""
    previous_active = db.scalars(
        select(ApiCredential).where(
            ApiCredential.organization_id == organization_id,
            ApiCredential.provider == PROVIDER,
            ApiCredential.is_active,
        )
    ).all()
    for previous in previous_active:
        previous.is_active = False
    db.flush()

    credential = ApiCredential(
        organization_id=organization_id,
        provider=PROVIDER,
        ticket_encrypted=crypto.encrypt(ticket),
        holder_name=holder_name,
        daily_limit=daily_limit,
        valid_until=valid_until,
        is_active=True,
    )
    db.add(credential)
    db.flush()
    return credential
