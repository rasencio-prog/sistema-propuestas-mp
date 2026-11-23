"""Verificacion de JWT de Supabase Auth (ADR-0003): firma via JWKS, expiracion, audiencia.

Los roles y la membresia de organizacion NO viven en el JWT: se resuelven desde `app.users` y
`app.organization_members` (ver sp.api.deps). Este modulo solo confirma que el token es autentico y
devuelve sus claims (en particular, `sub` = Supabase `auth.users.id`).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient

from sp.core.settings import get_settings

SUPABASE_AUDIENCE = "authenticated"


class InvalidTokenError(Exception):
    pass


def jwks_url(supabase_url: str) -> str:
    """Construye la URL del JWKS a partir del origen de SUPABASE_URL, descartando cualquier ruta.

    SUPABASE_URL a veces se pega con una ruta de otra seccion del panel (p. ej. `/rest/v1`); sin
    descartarla, la URL resultante queda mal formada (`.../rest/v1/auth/v1/.well-known/jwks.json`,
    que Supabase rechaza con 401) y el JWT se rechaza con un error enganoso de "token invalido",
    aunque la firma sea correcta (visto en la practica)."""
    parsed = urlsplit(supabase_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/auth/v1/.well-known/jwks.json"


@lru_cache
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(jwks_url(get_settings().supabase_url), cache_keys=True)


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
