"""0001 extensions.

Habilita pgvector (busqueda semantica, MVP-3) y citext (email case-insensitive en users) via
migracion, nunca a mano en el panel de Supabase (CLAUDE.md).

No crea el esquema `app` aqui: a diferencia de `CREATE EXTENSION`, Postgres exige el privilegio de
CREATE en la base de datos para `CREATE SCHEMA ... IF NOT EXISTS` **incluso si el esquema ya
existe** (comprobado en la practica: el rol restringido `test_runner` recibe "permission denied for
database postgres" aqui, aunque `app` ya exista). Por eso `app` (igual que `test`) se crea una sola
vez a mano, en el mismo paso del editor SQL de Supabase (README, ADR-0014 adenda), nunca desde una
migracion que deba poder correr tambien con el rol restringido.

Se asume (ADR-0014 y su adenda) que la primera vez que esta migracion corre es contra DATABASE_URL
(rol con privilegios suficientes en el proyecto Supabase). Cuando luego corra contra
TEST_DATABASE_URL (rol restringido test_runner), las extensiones ya existiran a nivel de base de
datos y "IF NOT EXISTS" no vuelve a requerir privilegios para crearlas.
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
