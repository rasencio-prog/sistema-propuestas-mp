"""Verificacion de JWT de Supabase Auth (ADR-0003): firma via JWKS, expiracion, audiencia.

Los roles y la membresia de organizacion NO viven en el JWT: se resuelven desde `app.users` y
`app.organization_members` (ver sp.api.deps). Este modulo solo confirma que el token es autentico y
devuelve sus claims (en particular, `sub` = Supabase `auth.users.id`).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from sp.core.settings import get_settings

SUPABASE_AUDIENCE = "authenticated"


class InvalidTokenError(Exception):
    pass


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


@dataclass(frozen=True)
class TokenClaims:
    auth_user_id: str
    email: str | None
    raw: dict[str, Any]


def decode_supabase_jwt(token: str, *, jwks_client: PyJWKClient | None = None) -> TokenClaims:
    """Decodifica y valida un JWT de Supabase Auth. Lanza InvalidTokenError si no es valido."""
    client = jwks_client or _jwks_client()
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=SUPABASE_AUDIENCE,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("El token no tiene 'sub'.")
    return TokenClaims(auth_user_id=sub, email=payload.get("email"), raw=payload)
