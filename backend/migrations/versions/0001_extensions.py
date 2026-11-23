"""0001 extensions.

Habilita pgvector (busqueda semantica, MVP-3) y citext (email case-insensitive en users) via
migracion, nunca a mano en el panel de Supabase (CLAUDE.md).

Se asume (ADR-0014) que la primera vez que esta migracion corre es contra DATABASE_URL (rol con
privilegios suficientes en el proyecto Supabase). Cuando luego corra contra TEST_DATABASE_URL (rol
restringido test_runner), la extension ya existira a nivel de base de datos y "IF NOT EXISTS" no
vuelve a intentar crearla.
"""

from __future__ import annotations

from alembic import op

revision = "0001_extensions"
down_revision: str | None = "procrastinate_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")


def downgrade() -> None:
    # No se eliminan extensiones en downgrade: podrian estar en uso por otros objetos.
    pass
