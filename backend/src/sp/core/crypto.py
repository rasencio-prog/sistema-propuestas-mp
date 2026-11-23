"""Cifrado en reposo (Fernet) para secretos guardados en la base, p. ej. el ticket de Mercado Publico.

CLAUDE.md: nunca poner secretos en codigo ni logs. La clave vive solo en APP_ENCRYPTION_KEY (.env).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from sp.core.settings import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().app_encryption_key.encode("utf-8"))


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode("utf-8")
