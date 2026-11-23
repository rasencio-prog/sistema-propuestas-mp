from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# backend/src/sp/core/settings.py -> repo root (donde vive .env, fuera de version control)
_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


def _ensure_search_path(url: str, default_schema: str) -> str:
    """Si la cadena de conexion no trae ya un `search_path` explicito (p. ej. copiada tal cual del
    panel de Supabase), le agrega `options=-csearch_path=<default_schema>` (ADR-0014). Si ya trae uno
    (como TEST_DATABASE_URL, con `search_path=test`), lo respeta sin tocarlo."""
    parsed = make_url(url)
    existing_options = parsed.query.get("options", "")
    if isinstance(existing_options, tuple):
        existing_options = " ".join(existing_options)
    if "search_path" in existing_options:
        return url

    new_options = f"-csearch_path={default_schema}"
    if existing_options:
        new_options = f"{existing_options} {new_options}"
    new_query = dict(parsed.query)
    new_query["options"] = new_options
    # str(url) enmascara la contrasena como "***" (pensado para logs); hace falta hide_password=False
    # para obtener la cadena de conexion real. Nunca loguear el resultado de esta funcion.
    return parsed.set(query=new_query).render_as_string(hide_password=False)


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
    def effective_database_url(self) -> str:
        """DATABASE_URL garantizando `search_path=app` (ADR-0014), aunque el valor pegado en .env no
        lo traiga. Usar siempre esta propiedad (nunca el campo `database_url` crudo) para conectar."""
        return _ensure_search_path(self.database_url, "app")

    @property
    def psycopg_conninfo(self) -> str:
        """`effective_database_url` en formato libpq (sin el prefijo de dialecto `+psycopg` de
        SQLAlchemy), para Procrastinate/psycopg directo (no via el engine de SQLAlchemy)."""
        return self.effective_database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
