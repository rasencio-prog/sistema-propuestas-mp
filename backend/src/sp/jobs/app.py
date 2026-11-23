"""App de Procrastinate (cola sobre Postgres, ADR-0001). Sin tareas todavia: el radar, el analisis
IA y la generacion de Excel se agregan en sus propias etapas (/p4 en adelante). Esta Etapa 1 solo
deja el worker arrancando y conectado, para validar la instalacion del esquema (docs/03, ADR-0014).
"""

from __future__ import annotations

from procrastinate import App, PsycopgConnector

from sp.core.db import extract_target_schema
from sp.core.settings import get_settings

_schema = extract_target_schema(get_settings().effective_database_url)


async def _configure_search_path(conn) -> None:  # noqa: ANN001
    # El Session Pooler de Supabase ignora el parametro de arranque "options" (PgBouncer): hace
    # falta un SET search_path explicito tras conectar (ver sp.core.db, ADR-0014).
    await conn.execute(f"SET search_path TO {_schema}, public")
    # psycopg3 abre conexiones con autocommit=False: sin este commit, psycopg_pool descarta la
    # conexion al terminar "configure" ("connection left in status INTRANS"), porque la deja con
    # una transaccion abierta en vez de en reposo (visto en la puesta en marcha real; ver
    # sp.core.db.attach_search_path, que tiene el mismo fix para el lado sincrono/SQLAlchemy).
    await conn.commit()


app = App(
    connector=PsycopgConnector(
        conninfo=get_settings().psycopg_conninfo,
        configure=_configure_search_path,
    )
)

# Import de las tareas despues de crear `app` (se registran en el por el decorador `@app.task`,
# efecto de borde necesario para que `procrastinate --app sp.jobs.app.app worker` las vea).
from sp.modules.radar import tasks as _radar_tasks  # noqa: E402,F401
