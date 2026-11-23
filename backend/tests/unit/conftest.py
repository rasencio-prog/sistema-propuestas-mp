from __future__ import annotations

from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet

from sp.core.crypto import _fernet
from sp.core.settings import get_settings

_FAKE_TEST_ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/postgres",
    "SUPABASE_URL": "https://example-project.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "APP_ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
}


@pytest.fixture(autouse=True)
def _isolated_settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Aisla las pruebas unitarias del .env real (CLAUDE.md: nunca leer/imprimir .env); usa valores
    ficticios. Solo en tests/unit/ (no en tests/integration/, que necesita el TEST_DATABASE_URL real
    del .env; visto en la practica: puesto en tests/conftest.py afectaba tambien a integracion)."""
    for key, value in _FAKE_TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    _fernet.cache_clear()
    yield
    get_settings.cache_clear()
    _fernet.cache_clear()
