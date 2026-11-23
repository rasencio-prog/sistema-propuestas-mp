from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sp.core.db import Base, attach_search_path, extract_target_schema
from sp.core.settings import get_settings

# Importar los modulos de modelos para que su metadata quede registrada en Base.metadata
# (ADR-0014: sin schema= explicito; el search_path de la conexion decide el esquema destino).
from sp.modules.audit import models as audit_models  # noqa: F401
from sp.modules.organizations import models as organizations_models  # noqa: F401
from sp.modules.service_lines import models as service_lines_models  # noqa: F401
from sp.modules.users import models as users_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().effective_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # transaction_per_migration=True: cada revision confirma por separado. Las de Procrastinate ya
    # se auto-confirman via `context.autocommit_block()` (migrations_utils.run_procrastinate_sql);
    # sin esta opcion, un fallo en CUALQUIER migracion posterior revierte tambien el registro de
    # version_num de las que ya corrieron en modo autocommit, dejando el `alembic_version` desalineado
    # con lo que de verdad quedo aplicado (visto en la puesta en marcha real: ver docs/decisions/ADR-0014).
    url = get_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    # El Session Pooler de Supabase ignora el parametro de arranque "options" (PgBouncer): hace
    # falta un SET search_path explicito tras conectar (ver sp.core.db, ADR-0014).
    attach_search_path(connectable, extract_target_schema(url))

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
