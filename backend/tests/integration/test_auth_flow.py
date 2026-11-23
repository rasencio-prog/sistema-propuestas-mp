"""Cadena completa de autenticacion (JWT -> usuario -> membresia -> rol) contra el esquema `test`.

JWT firmados localmente (sin red, sin Supabase real): se sustituye el cliente JWKS de
sp.core.security por uno que devuelve la clave publica fija de la prueba (ver tests/unit/test_security.py
para la verificacion aislada del propio decodificador).
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text

import sp.core.security as security_module
from sp.api.deps import get_current_user


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def _fake_jwks(monkeypatch: pytest.MonkeyPatch, rsa_keypair):
    _private_key, public_key = rsa_keypair

    class _FakeSigningKey:
        key = public_key

    class _FakeJWKSClient:
        def get_signing_key_from_jwt(self, _token: str) -> _FakeSigningKey:
            return _FakeSigningKey()

    monkeypatch.setattr(security_module, "_jwks_client", lambda: _FakeJWKSClient())


def _token(private_key, *, sub: str, exp_delta: int = 3600) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": "robinson@example.com",
        "aud": security_module.SUPABASE_AUDIENCE,
        "iat": now,
        "exp": now + exp_delta,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _seed_user_with_membership(db_session, *, auth_user_id: str, role: str = "admin"):
    org_id = db_session.execute(
        text("INSERT INTO organizations (legal_name) VALUES ('Org de prueba') RETURNING id")
    ).scalar_one()
    user_id = db_session.execute(
        text(
            "INSERT INTO users (auth_user_id, email) VALUES (:auth_user_id, 'robinson@example.com') "
            "RETURNING id"
        ),
        {"auth_user_id": auth_user_id},
    ).scalar_one()
    db_session.execute(
        text(
            "INSERT INTO organization_members (organization_id, user_id, role) "
            "VALUES (:org_id, :user_id, :role)"
        ),
        {"org_id": org_id, "user_id": user_id, "role": role},
    )
    db_session.flush()
    return org_id, user_id


def test_valid_token_with_membership_resolves_role(db_session, rsa_keypair) -> None:
    private_key, _public_key = rsa_keypair
    auth_user_id = str(uuid.uuid4())
    org_id, user_id = _seed_user_with_membership(db_session, auth_user_id=auth_user_id, role="commercial")

    token = _token(private_key, sub=auth_user_id)
    current_user = get_current_user(credentials=_credentials(token), db=db_session)

    assert current_user.user_id == user_id
    assert current_user.organization_id == org_id
    assert current_user.role == "commercial"


def test_expired_token_is_401(db_session, rsa_keypair) -> None:
    private_key, _public_key = rsa_keypair
    token = _token(private_key, sub=str(uuid.uuid4()), exp_delta=-60)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_token_signed_with_wrong_key_is_401(db_session) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _token(other_key, sub=str(uuid.uuid4()))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_valid_token_without_user_row_is_403(db_session, rsa_keypair) -> None:
    private_key, _public_key = rsa_keypair
    token = _token(private_key, sub=str(uuid.uuid4()))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)
    assert exc_info.value.status_code == 403


def test_valid_token_without_membership_is_403(db_session, rsa_keypair) -> None:
    private_key, _public_key = rsa_keypair
    auth_user_id = str(uuid.uuid4())
    db_session.execute(
        text("INSERT INTO users (auth_user_id, email) VALUES (:auth_user_id, 'sin-membresia@example.com')"),
        {"auth_user_id": auth_user_id},
    )
    db_session.flush()

    token = _token(private_key, sub=auth_user_id)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=_credentials(token), db=db_session)
    assert exc_info.value.status_code == 403
