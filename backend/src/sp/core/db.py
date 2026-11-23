"""Engine y sesiones de SQLAlchemy.

El esquema de destino ("app" en desarrollo/produccion, "test" en pruebas de integracion) lo decide el
`search_path` de la sesion, no el codigo de los modelos/migraciones (ADR-0014): ninguno califica el
esquema. El `search_path` se fuerza con un `SET` justo despues de conectar (`attach_search_path`),
no confiando en el parametro de arranque `options` de la cadena de conexion: el Session Pooler de
Supabase (PgBouncer) lo ignora en silencio (confirmado en la puesta en marcha real; ver ADR-0014).
"""

from __future__ import annotations

import re
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from sp.core.settings import get_settings

_SEARCH_PATH_RE = re.compile(r"-csearch_path=([A-Za-z_][A-Za-z0-9_]*)")


class Base(DeclarativeBase):
    pass


def extract_target_schema(database_url: str, default: str = "app") -> str:
    """Lee el esquema destino desde `options=-csearch_path=<esquema>` en la URL. Es solo una
    convencion propia (ver `effective_database_url`/`_ensure_search_path` en settings.py): el valor
    real que manda es el `SET search_path` que aplica `attach_search_path`, no este parametro."""
    parsed = make_url(database_url)
    options = parsed.query.get("options", "")
    if isinstance(options, tuple):
        options = " ".join(options)
    match = _SEARCH_PATH_RE.search(options)
    return match.group(1) if match else default


def attach_search_path(engine: Engine, schema: str) -> None:
    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"SET search_path TO {schema}, public")
        finally:
            cursor.close()
        # psycopg3 abre conexiones con autocommit=False: sin este commit, un ROLLBACK posterior en
        # la misma conexion (p. ej. al reciclarla el pool, o una transaccion explicita que se
        # deshace) tambien deshace el SET search_path de arriba, dejando la sesion en el esquema
        # por defecto. Visto en la puesta en marcha real (ADR-0014, adenda).
        dbapi_connection.commit()


def make_engine(database_url: str, schema: str | None = None) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)
    attach_search_path(engine, schema or extract_target_schema(database_url))
    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().effective_database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
