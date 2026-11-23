"""0005 no affinity score cap.

Ajuste de la etapa /p4-radar (23-11-2026, segunda revision, ADR-0017 addendum): la afinidad de linea
de servicio pasa de ser solo un factor ponderado mas a tambien una condicion. Sin coincidencia con
ninguna linea activa, el puntaje final queda acotado a `thresholds.no_affinity_score_cap` (default
15), sin importar monto ni plazo -- evita que licitaciones fuera de rubro (ej. obras civiles,
inspeccion tecnica) saquen puntajes moderados/altos solo por monto y plazo atractivos (caso real:
dos licitaciones de Putaendo con 46.13 puntos sin afinidad TI).

Fusiona la nueva clave en `scoring_profiles.thresholds` ya sembrados por `0004`, sin pisar un valor
que un administrador ya haya editado a mano (solo agrega la clave si todavia no existe).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_no_affinity_score_cap"
down_revision: str | None = "0004_radar_opportunities"
branch_labels = None
depends_on = None

_DEFAULT_CAP = 15


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE scoring_profiles
            SET thresholds = thresholds || jsonb_build_object('no_affinity_score_cap', :cap)
            WHERE NOT (thresholds ? 'no_affinity_score_cap')
            """
        ),
        {"cap": _DEFAULT_CAP},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE scoring_profiles SET thresholds = thresholds - 'no_affinity_score_cap'"))
