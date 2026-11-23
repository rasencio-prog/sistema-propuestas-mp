"""Modelos de `opportunities` y sus tablas satelite (docs/03 S2, S3; ADR-0006, ADR-0010)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sp.core.db import Base

_INTERNAL_STATUSES = (
    "detectada",
    "preseleccionada",
    "descartada_preseleccion",
    "documentos_pendientes",
    "cerrada_sin_decision",
)

_DATE_TYPES = (
    "publication",
    "questions_close",
    "answers_publication",
    "offers_close",
    "technical_opening",
    "economic_opening",
    "award_estimated",
    "award_actual",
    "support_physical",
    "evaluation_time",
    "estimated_signature",
    "site_visit",
    "background_delivery",
    "user_dates",
)


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = (
        UniqueConstraint("source", "organism_code", "unit_code", name="uq_buyers_source_organism_unit"),
        Index("ix_buyers_region", "region"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="mercado_publico")
    organism_code: Mapped[str] = mapped_column(String, nullable=False)
    organism_name: Mapped[str] = mapped_column(String, nullable=False)
    unit_code: Mapped[str] = mapped_column(String, nullable=False)
    unit_name: Mapped[str] = mapped_column(String, nullable=False)
    unit_rut: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    commune: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("source", "official_code", name="uq_opportunities_source_code"),
        CheckConstraint(
            "internal_status IN " + str(_INTERNAL_STATUSES),
            name="ck_opportunities_internal_status",
        ),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_opportunities_score_range"),
        Index("ix_opportunities_official_status_code", "official_status_code"),
        Index("ix_opportunities_buyer_id", "buyer_id"),
        Index("ix_opportunities_internal_status_score", "internal_status", "score"),
        Index(
            "ix_opportunities_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="mercado_publico")
    official_code: Mapped[str] = mapped_column(String, nullable=False)

    opportunity_type_code: Mapped[str | None] = mapped_column(String, nullable=True)
    opportunity_type_text: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    buyer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    estimated_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    amount_visibility: Mapped[str] = mapped_column(String, nullable=False, server_default="unknown")

    official_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    official_status_text: Mapped[str] = mapped_column(String, nullable=False)
    official_status_documented: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    internal_status: Mapped[str] = mapped_column(String, nullable=False, server_default="detectada")
    internal_status_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scoring_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    classification_justification: Mapped[str | None] = mapped_column(String, nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    source_url: Mapped[str | None] = mapped_column(String, nullable=True)

    contract_duration_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_duration_unit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_renewable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    renewal_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    renewal_period_text: Mapped[str | None] = mapped_column(String, nullable=True)
    subcontracting_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    contract_formalization_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_modality_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_type_code: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_responsible_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_responsible_email: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_responsible_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_responsible_name: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_responsible_email: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_complaints_count_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_standard_type: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    award_act_type_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    award_act_number: Mapped[str | None] = mapped_column(String, nullable=True)
    award_offerors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    award_act_url: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_list: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    detail_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class OpportunityItem(Base):
    __tablename__ = "opportunity_items"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "line_no", name="uq_opportunity_items_opportunity_line"),
        Index("ix_opportunity_items_category_code", "category_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_code: Mapped[str | None] = mapped_column(String, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)


class OpportunityDate(Base):
    __tablename__ = "opportunity_dates"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "date_type", name="uq_opportunity_dates_opportunity_type"),
        CheckConstraint("date_type IN " + str(_DATE_TYPES), name="ck_opportunity_dates_date_type"),
        CheckConstraint(
            "parse_status IN ('ok','unparseable','missing')", name="ck_opportunity_dates_parse_status"
        ),
        Index("ix_opportunity_dates_type_value", "date_type", "value_utc"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date_type: Mapped[str] = mapped_column(String, nullable=False)
    value_utc: Mapped[datetime | None] = mapped_column(nullable=True)
    original_text: Mapped[str | None] = mapped_column(String, nullable=True)
    source_field: Mapped[str | None] = mapped_column(String, nullable=True)
    parse_status: Mapped[str] = mapped_column(String, nullable=False)


class OpportunityChange(Base):
    __tablename__ = "opportunity_changes"
    __table_args__ = (
        CheckConstraint(
            "change_type IN ('status','date','amount','other')", name="ck_opportunity_changes_type"
        ),
        Index("ix_opportunity_changes_opportunity_detected", "opportunity_id", "detected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    radar_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    requires_reanalysis: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    detected_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class OpportunityServiceLine(Base):
    __tablename__ = "opportunity_service_lines"
    __table_args__ = (Index("ix_opportunity_service_lines_service_line_id", "service_line_id"),)

    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    service_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    method: Mapped[str] = mapped_column(String, primary_key=True)
    matched_terms: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    matched_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    justification: Mapped[str | None] = mapped_column(String, nullable=True)


__all__ = [
    "Buyer",
    "Opportunity",
    "OpportunityItem",
    "OpportunityDate",
    "OpportunityChange",
    "OpportunityServiceLine",
]
