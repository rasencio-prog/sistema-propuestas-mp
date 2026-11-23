"""JWT de prueba firmados localmente (ADR-0003, docs/07): sin red, sin Supabase real."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from sp.core.security import SUPABASE_AUDIENCE, InvalidTokenError, decode_supabase_jwt


@dataclass
class _FakeSigningKey:
    key: object


class _FakeJWKSClient:
    """Sustituye a PyJWKClient: siempre devuelve la clave publica fija de la prueba."""

    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, _token: str) -> _FakeSigningKey:
        return _FakeSigningKey(key=self._public_key)


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(private_key, *, sub: str, aud: str = SUPABASE_AUDIENCE, exp_delta: int = 3600) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": "robinson@example.com",
        "aud": aud,
        "iat": now,
        "exp": now + exp_delta,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_decode_valid_token(rsa_keypair) -> None:
    private_key, public_key = rsa_keypair
    auth_user_id = str(uuid.uuid4())
    token = _make_token(private_key, sub=auth_user_id)

    claims = decode_supabase_jwt(token, jwks_client=_FakeJWKSClient(public_key))

    assert claims.auth_user_id == auth_user_id
    assert claims.email == "robinson@example.com"


def test_decode_expired_token_is_rejected(rsa_keypair) -> None:
    private_key, public_key = rsa_keypair
    token = _make_token(private_key, sub=str(uuid.uuid4()), exp_delta=-10)

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token, jwks_client=_FakeJWKSClient(public_key))


def test_decode_wrong_audience_is_rejected(rsa_keypair) -> None:
    private_key, public_key = rsa_keypair
    token = _make_token(private_key, sub=str(uuid.uuid4()), aud="otro-audience")

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token, jwks_client=_FakeJWKSClient(public_key))


def test_decode_wrong_signature_is_rejected(rsa_keypair) -> None:
    _private_key, public_key = rsa_keypair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(other_private_key, sub=str(uuid.uuid4()))

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token, jwks_client=_FakeJWKSClient(public_key))


def test_decode_token_without_sub_is_rejected(rsa_keypair) -> None:
    private_key, public_key = rsa_keypair
    now = int(time.time())
    payload = {"aud": SUPABASE_AUDIENCE, "iat": now, "exp": now + 3600}
    token = jwt.encode(payload, private_key, algorithm="RS256")

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token, jwks_client=_FakeJWKSClient(public_key))
