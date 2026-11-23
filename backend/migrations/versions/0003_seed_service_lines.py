"""0003 seed service lines.

Semilla idempotente (docs/05-backlog E1-4): una organizacion ("Databrain SpA", docs/00-decisiones-
propietario.md) y las 5 lineas de servicio del brief (seccion 2), con sus palabras clave positivas.
Rubros (category_codes) y palabras de exclusion quedan vacios hasta /p2 (docs/05-backlog E1-4).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_seed_service_lines"
down_revision: str | None = "0002_app_foundations"
branch_labels = None
depends_on = None

ORGANIZATION_LEGAL_NAME = "Databrain SpA"

SEED_SERVICE_LINES: list[dict[str, object]] = [
    {
        "name": "Desarrollo de software",
        "description": (
            "Sistemas web y aplicaciones; desarrollo de plataformas; integraciones y APIs; "
            "mantenimiento evolutivo; modernizacion de sistemas."
        ),
        "positive_keywords": [
            "sistemas web",
            "aplicaciones",
            "desarrollo de plataformas",
            "integraciones",
            "APIs",
            "mantenimiento evolutivo",
            "modernizacion de sistemas",
        ],
    },
    {
        "name": "Soporte y servicios informáticos",
        "description": (
            "Soporte tecnico; mesa de ayuda; administracion de sistemas; mantenimiento informatico; "
            "soporte de infraestructura."
        ),
        "positive_keywords": [
            "soporte tecnico",
            "mesa de ayuda",
            "administracion de sistemas",
            "mantenimiento informatico",
            "soporte de infraestructura",
        ],
    },
    {
        "name": "Consultoría TI",
        "description": (
            "Diagnosticos tecnologicos; arquitectura de soluciones; transformacion digital; "
            "auditorias y levantamientos; planes de implementacion."
        ),
        "positive_keywords": [
            "diagnosticos tecnologicos",
            "arquitectura de soluciones",
            "transformacion digital",
            "auditorias y levantamientos",
            "planes de implementacion",
        ],
    },
    {
        "name": "Cloud y servicios tecnológicos",
        "description": (
            "Migracion cloud; infraestructura en la nube; administracion de servidores; respaldos; "
            "continuidad operacional; monitoreo y optimizacion."
        ),
        "positive_keywords": [
            "migracion cloud",
            "infraestructura en la nube",
            "administracion de servidores",
            "respaldos",
            "continuidad operacional",
            "monitoreo y optimizacion",
        ],
    },
    {
        "name": "Automatización e IA",
        "description": (
            "Automatizacion de procesos; agentes inteligentes; asistentes conversacionales; "
            "integracion de IA; automatizacion documental."
        ),
        "positive_keywords": [
            "automatizacion de procesos",
            "agentes inteligentes",
            "asistentes conversacionales",
            "integracion de IA",
            "automatizacion documental",
        ],
    },
]


def _get_or_create_organization(conn: sa.Connection) -> object:
    existing = conn.execute(
        sa.text("SELECT id FROM organizations WHERE legal_name = :legal_name AND deleted_at IS NULL"),
        {"legal_name": ORGANIZATION_LEGAL_NAME},
    ).scalar()
    if existing is not None:
        return existing

    return conn.execute(
        sa.text("INSERT INTO organizations (legal_name) VALUES (:legal_name) RETURNING id"),
        {"legal_name": ORGANIZATION_LEGAL_NAME},
    ).scalar_one()


def upgrade() -> None:
    conn = op.get_bind()
    organization_id = _get_or_create_organization(conn)

    for line in SEED_SERVICE_LINES:
        conn.execute(
            sa.text(
                """
                INSERT INTO service_lines
                    (organization_id, name, description, positive_keywords,
                     exclusion_keywords, category_codes)
                SELECT :organization_id, :name, :description, :positive_keywords, '{}', '{}'
                WHERE NOT EXISTS (
                    SELECT 1 FROM service_lines
                    WHERE organization_id = :organization_id
                      AND lower(name) = lower(:name)
                      AND deleted_at IS NULL
                )
                """
            ),
            {
                "organization_id": organization_id,
                "name": line["name"],
                "description": line["description"],
                "positive_keywords": line["positive_keywords"],
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM service_lines WHERE organization_id = "
            "(SELECT id FROM organizations WHERE legal_name = :legal_name)"
        ),
        {"legal_name": ORGANIZATION_LEGAL_NAME},
    )
    conn.execute(
        sa.text("DELETE FROM organizations WHERE legal_name = :legal_name"),
        {"legal_name": ORGANIZATION_LEGAL_NAME},
    )
