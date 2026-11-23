"""0002 app foundations.

Tablas de la Etapa 1 (docs/03): organizations, users, organization_members, api_credentials,
service_lines, audit_events. RLS activado y sin politicas (ADR-0002): bloquea a cualquier rol de
Supabase que no sea el que usa la app (hoy, tablas en el esquema destino por `search_path`, no en
`public`, asi que ademas no quedan expuestas por la Data API).

Sin `schema=` en ninguna tabla/indice (ADR-0014): el `search_path` de la conexion decide si esto
termina en `app` (DATABASE_URL) o en `test` (TEST_DATABASE_URL).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID

revision = "0002_app_foundations"
down_revision: str | None = "0001_extensions"
branch_labels = None
depends_on = None

_TABLES_WITH_RLS = [
    "organizations",
    "users",
    "organization_members",
    "api_credentials",
    "service_lines",
    "audit_events",
]


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("rut", sa.String(), nullable=True),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_organizations_rut_unique",
        "organizations",
        ["rut"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("auth_user_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("email", CITEXT(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("auth_provider", sa.String(), nullable=False, server_default="supabase"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
    )

    op.create_table(
        "organization_members",
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            primary_key=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('admin','commercial','reviewer','read_only')",
            name="ck_organization_members_role",
        ),
    )
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    op.create_table(
        "api_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="mercado_publico"),
        sa.Column("ticket_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("holder_name", sa.String(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="8000"),
        sa.Column("max_rps", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("daily_limit BETWEEN 1 AND 10000", name="ck_api_credentials_daily_limit"),
    )
    op.create_index(
        "ix_api_credentials_org_provider_active",
        "api_credentials",
        ["organization_id", "provider"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "service_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "positive_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "exclusion_keywords",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("category_codes", sa.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_service_lines_org_name_unique",
        "service_lines",
        ["organization_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_service_lines_positive_keywords",
        "service_lines",
        ["positive_keywords"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_service_lines_category_codes",
        "service_lines",
        ["category_codes"],
        postgresql_using="gin",
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("ip", INET(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("actor_type IN ('user','system')", name="ck_audit_events_actor_type"),
    )
    op.create_index("ix_audit_events_org_occurred", "audit_events", ["organization_id", "occurred_at"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])

    # audit_events es de solo insercion (docs/03 S3): un trigger lo garantiza para cualquier rol,
    # incluido el dueno de la tabla (REVOKE no alcanza al dueno en Postgres).
    op.execute(
        """
        CREATE FUNCTION audit_events_block_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events es de solo insercion (CLAUDE.md, docs/03 S3)';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_block_mutation
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_mutation()
        """
    )

    for table in _TABLES_WITH_RLS:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_block_mutation ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_block_mutation()")
    op.drop_table("audit_events")
    op.drop_table("service_lines")
    op.drop_table("api_credentials")
    op.drop_table("organization_members")
    op.drop_table("users")
    op.drop_table("organizations")
