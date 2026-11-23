"""0004 radar opportunities.

Tablas del radar (docs/03, ADR-0010): buyers, opportunities + satelites (items, dates, changes,
service_lines), scoring_profiles, radar_runs, api_quota_usage, api_call_log. La tabla `bids` NO se
crea aqui (nace con "Descargar", ADR-0006, migracion de `/p5-excel1`).

`pg_trgm` se agrega con `SCHEMA public` explicito (mismo patron que `0001_extensions`, ADR-0016):
necesario para el indice GIN de busqueda por texto en `opportunities.title`.

Semillas idempotentes: un `scoring_profiles` activo por defecto (ADR-0017) y, solo si `MP_TICKET`
esta en el entorno, una fila de `api_credentials` cifrada (ADR-0018, bridge hasta que exista E1-7).
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sp.core import crypto
from sp.core.settings import get_settings

revision = "0004_radar_opportunities"
down_revision: str | None = "0003_seed_service_lines"
branch_labels = None
depends_on = None

_TABLES_WITH_RLS = [
    "buyers",
    "opportunities",
    "opportunity_items",
    "opportunity_dates",
    "opportunity_changes",
    "opportunity_service_lines",
    "scoring_profiles",
    "radar_runs",
    "api_quota_usage",
    "api_call_log",
]

_ORGANIZATION_LEGAL_NAME = "Databrain SpA"

_DEFAULT_WEIGHTS = {
    "service_line_affinity": 0.40,
    "time_viability": 0.15,
    "economic_attractiveness": 0.20,
    "operational_capacity": 0.10,
    "contractual_risk": 0.15,
}

_DEFAULT_THRESHOLDS = {
    "min_days_to_close": 3,
    "top_n": 50,
    "min_score_include": 40,
    "time_viability_full_score_days": 30,
    "economic_attractive_min": 5_000_000,
    "economic_attractive_max": 150_000_000,
    "economic_default_when_not_visible": 50,
    "operational_ideal_min_months": 1,
    "operational_ideal_max_months": 36,
    "operational_default_when_unknown": 50,
    "risk_complaints_low": 0,
    "risk_complaints_high": 500,
    "risk_default_when_unknown": 50,
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public")

    op.create_table(
        "buyers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(), nullable=False, server_default="mercado_publico"),
        sa.Column("organism_code", sa.String(), nullable=False),
        sa.Column("organism_name", sa.String(), nullable=False),
        sa.Column("unit_code", sa.String(), nullable=False),
        sa.Column("unit_name", sa.String(), nullable=False),
        sa.Column("unit_rut", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("commune", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source", "organism_code", "unit_code", name="uq_buyers_source_organism_unit"),
    )
    op.create_index("ix_buyers_region", "buyers", ["region"])

    op.create_table(
        "opportunities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(), nullable=False, server_default="mercado_publico"),
        sa.Column("official_code", sa.String(), nullable=False),
        sa.Column("opportunity_type_code", sa.String(), nullable=True),
        sa.Column("opportunity_type_text", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("buyer_id", UUID(as_uuid=True), sa.ForeignKey("buyers.id"), nullable=True),
        sa.Column("estimated_amount", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("amount_visibility", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("official_status_code", sa.Integer(), nullable=False),
        sa.Column("official_status_text", sa.String(), nullable=False),
        sa.Column("official_status_documented", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("internal_status", sa.String(), nullable=False, server_default="detectada"),
        sa.Column("internal_status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("score_breakdown", JSONB(), nullable=True),
        sa.Column("scoring_profile_id", UUID(as_uuid=True), nullable=True),
        sa.Column("classification_justification", sa.String(), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("contract_duration_value", sa.Integer(), nullable=True),
        sa.Column("contract_duration_unit_code", sa.Integer(), nullable=True),
        sa.Column("is_renewable", sa.Boolean(), nullable=True),
        sa.Column("renewal_value", sa.Integer(), nullable=True),
        sa.Column("renewal_period_text", sa.String(), nullable=True),
        sa.Column("subcontracting_allowed", sa.Boolean(), nullable=True),
        sa.Column("contract_formalization_code", sa.Integer(), nullable=True),
        sa.Column("payment_modality_code", sa.Integer(), nullable=True),
        sa.Column("payment_type_code", sa.String(), nullable=True),
        sa.Column("contract_responsible_name", sa.String(), nullable=True),
        sa.Column("contract_responsible_email", sa.String(), nullable=True),
        sa.Column("contract_responsible_phone", sa.String(), nullable=True),
        sa.Column("payment_responsible_name", sa.String(), nullable=True),
        sa.Column("payment_responsible_email", sa.String(), nullable=True),
        sa.Column("buyer_complaints_count_snapshot", sa.Integer(), nullable=True),
        sa.Column("is_standard_type", sa.Boolean(), nullable=True),
        sa.Column("award_act_type_code", sa.Integer(), nullable=True),
        sa.Column("award_act_number", sa.String(), nullable=True),
        sa.Column("award_offerors_count", sa.Integer(), nullable=True),
        sa.Column("award_act_url", sa.String(), nullable=True),
        sa.Column("raw_list", JSONB(), nullable=True),
        sa.Column("raw_detail", JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("detail_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source", "official_code", name="uq_opportunities_source_code"),
        sa.CheckConstraint(
            "internal_status IN ('detectada','preseleccionada','descartada_preseleccion',"
            "'documentos_pendientes','cerrada_sin_decision')",
            name="ck_opportunities_internal_status",
        ),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_opportunities_score_range"),
    )
    op.create_index("ix_opportunities_official_status_code", "opportunities", ["official_status_code"])
    op.create_index("ix_opportunities_buyer_id", "opportunities", ["buyer_id"])
    op.create_index("ix_opportunities_internal_status_score", "opportunities", ["internal_status", "score"])
    op.execute("CREATE INDEX ix_opportunities_title_trgm ON opportunities USING gin (title gin_trgm_ops)")

    op.create_table(
        "opportunity_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id"),
            nullable=False,
        ),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.Integer(), nullable=True),
        sa.Column("category_code", sa.String(), nullable=True),
        sa.Column("category_name", sa.String(), nullable=True),
        sa.Column("product_name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.UniqueConstraint("opportunity_id", "line_no", name="uq_opportunity_items_opportunity_line"),
    )
    op.create_index("ix_opportunity_items_category_code", "opportunity_items", ["category_code"])

    op.create_table(
        "opportunity_dates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id"),
            nullable=False,
        ),
        sa.Column("date_type", sa.String(), nullable=False),
        sa.Column("value_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_text", sa.String(), nullable=True),
        sa.Column("source_field", sa.String(), nullable=True),
        sa.Column("parse_status", sa.String(), nullable=False),
        sa.UniqueConstraint("opportunity_id", "date_type", name="uq_opportunity_dates_opportunity_type"),
        sa.CheckConstraint(
            "date_type IN ('publication','questions_close','answers_publication','offers_close',"
            "'technical_opening','economic_opening','award_estimated','award_actual',"
            "'support_physical','evaluation_time','estimated_signature','site_visit',"
            "'background_delivery','user_dates')",
            name="ck_opportunity_dates_date_type",
        ),
        sa.CheckConstraint(
            "parse_status IN ('ok','unparseable','missing')", name="ck_opportunity_dates_parse_status"
        ),
    )
    op.create_index("ix_opportunity_dates_type_value", "opportunity_dates", ["date_type", "value_utc"])

    op.create_table(
        "opportunity_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("radar_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("old_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=True),
        sa.Column("requires_reanalysis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "change_type IN ('status','date','amount','other')", name="ck_opportunity_changes_type"
        ),
    )
    op.create_index(
        "ix_opportunity_changes_opportunity_detected",
        "opportunity_changes",
        ["opportunity_id", "detected_at"],
    )

    op.create_table(
        "scoring_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("thresholds", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "version", name="uq_scoring_profiles_org_version"),
    )
    op.create_index(
        "ix_scoring_profiles_org_active_unique",
        "scoring_profiles",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # opportunities.scoring_profile_id se agrega como FK diferida (la tabla referenciada se crea
    # recien arriba, en esta misma migracion).
    op.create_foreign_key(
        "fk_opportunities_scoring_profile",
        "opportunities",
        "scoring_profiles",
        ["scoring_profile_id"],
        ["id"],
    )

    op.create_table(
        "opportunity_service_lines",
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("service_line_id", UUID(as_uuid=True), sa.ForeignKey("service_lines.id"), primary_key=True),
        sa.Column("method", sa.String(), primary_key=True),
        sa.Column("matched_terms", sa.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("matched_codes", sa.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("justification", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_opportunity_service_lines_service_line_id", "opportunity_service_lines", ["service_line_id"]
    )

    op.create_table(
        "radar_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("radar_date", sa.Date(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("listed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detailed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("trigger IN ('scheduled','manual')", name="ck_radar_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('running','succeeded','partial','failed')", name="ck_radar_runs_status"
        ),
    )
    op.create_index(
        "ix_radar_runs_org_date_succeeded_unique",
        "radar_runs",
        ["organization_id", "radar_date"],
        unique=True,
        postgresql_where=sa.text("status = 'succeeded'"),
    )
    op.create_index("ix_radar_runs_org_started", "radar_runs", ["organization_id", "started_at"])

    op.create_foreign_key(
        "fk_opportunity_changes_radar_run", "opportunity_changes", "radar_runs", ["radar_run_id"], ["id"]
    )

    op.create_table(
        "api_quota_usage",
        sa.Column("credential_id", UUID(as_uuid=True), sa.ForeignKey("api_credentials.id"), primary_key=True),
        sa.Column("quota_date", sa.Date(), primary_key=True),
        sa.Column("requests_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "api_call_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("credential_id", UUID(as_uuid=True), sa.ForeignKey("api_credentials.id"), nullable=False),
        sa.Column("radar_run_id", UUID(as_uuid=True), sa.ForeignKey("radar_runs.id"), nullable=True),
        sa.Column("endpoint_name", sa.String(), nullable=False),
        sa.Column("params_sanitized", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_api_call_log_credential_called", "api_call_log", ["credential_id", "called_at"])
    op.create_index("ix_api_call_log_radar_run", "api_call_log", ["radar_run_id"])

    for table in _TABLES_WITH_RLS:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    _seed_scoring_profile()
    _seed_api_credential()


def _get_organization_id(conn: sa.Connection) -> object | None:
    return conn.execute(
        sa.text("SELECT id FROM organizations WHERE legal_name = :name AND deleted_at IS NULL"),
        {"name": _ORGANIZATION_LEGAL_NAME},
    ).scalar()


def _seed_scoring_profile() -> None:
    conn = op.get_bind()
    organization_id = _get_organization_id(conn)
    if organization_id is None:
        return

    already_exists = conn.execute(
        sa.text("SELECT 1 FROM scoring_profiles WHERE organization_id = :org_id AND version = 1"),
        {"org_id": organization_id},
    ).scalar()
    if already_exists is not None:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO scoring_profiles (organization_id, version, weights, thresholds, is_active)
            VALUES (:org_id, 1, CAST(:weights AS jsonb), CAST(:thresholds AS jsonb), true)
            """
        ),
        {
            "org_id": organization_id,
            "weights": json.dumps(_DEFAULT_WEIGHTS),
            "thresholds": json.dumps(_DEFAULT_THRESHOLDS),
        },
    )


def _seed_api_credential() -> None:
    """ADR-0018: bridge hasta que exista el endpoint de E1-7. No hace nada si `MP_TICKET` no esta
    en el entorno (p. ej. en CI)."""
    settings = get_settings()
    if not settings.mp_ticket:
        return

    conn = op.get_bind()
    organization_id = _get_organization_id(conn)
    if organization_id is None:
        return

    already_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM api_credentials WHERE organization_id = :org_id "
            "AND provider = 'mercado_publico' AND is_active"
        ),
        {"org_id": organization_id},
    ).scalar()
    if already_exists is not None:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO api_credentials
                (organization_id, provider, ticket_encrypted, holder_name, daily_limit, is_active)
            VALUES (:org_id, 'mercado_publico', :ticket_encrypted, 'Robinson Asencio', 8000, true)
            """
        ),
        {"org_id": organization_id, "ticket_encrypted": crypto.encrypt(settings.mp_ticket)},
    )


def _unseed_api_credential() -> None:
    """Deshace `_seed_api_credential`: sin esto, el downgrade de `0003` (que borra la organizacion
    'Databrain SpA') choca con la FK de `api_credentials` hacia esa misma fila sembrada aqui."""
    conn = op.get_bind()
    organization_id = _get_organization_id(conn)
    if organization_id is None:
        return
    conn.execute(
        sa.text(
            "DELETE FROM api_credentials WHERE organization_id = :org_id AND provider = 'mercado_publico'"
        ),
        {"org_id": organization_id},
    )


def downgrade() -> None:
    _unseed_api_credential()
    op.drop_table("api_call_log")
    op.drop_table("api_quota_usage")
    op.drop_constraint("fk_opportunity_changes_radar_run", "opportunity_changes", type_="foreignkey")
    op.drop_table("radar_runs")
    op.drop_table("opportunity_service_lines")
    op.drop_constraint("fk_opportunities_scoring_profile", "opportunities", type_="foreignkey")
    op.drop_table("scoring_profiles")
    op.drop_table("opportunity_changes")
    op.drop_table("opportunity_dates")
    op.drop_table("opportunity_items")
    op.drop_table("opportunities")
    op.drop_table("buyers")
