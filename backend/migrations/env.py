from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sp.core.db import Base
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
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
