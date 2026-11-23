from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/sp/core/settings.py -> repo root (donde vive .env, fuera de version control)
_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    test_database_url: str | None = None

    supabase_url: str
    supabase_anon_key: str

    app_encryption_key: str

    mp_ticket: str | None = None

    cors_allowed_origins: str = "http://localhost:5173"

    log_level: str = "INFO"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def psycopg_conninfo(self) -> str:
        """DATABASE_URL en formato libpq (sin el prefijo de dialecto `+psycopg` de SQLAlchemy),
        para Procrastinate/psycopg directo (no via el engine de SQLAlchemy)."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
