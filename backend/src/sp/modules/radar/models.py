"""Tablas de infraestructura del radar (docs/03 S2, S3): corridas, cuota diaria y bitacora de
llamadas. Nunca guardan el ticket (CLAUDE.md); `params_sanitized` son los parametros de la llamada
(fecha/codigo), nunca incluye `ticket`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sp.core.db import Base


class RadarRun(Base):
    __tablename__ = "radar_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled','manual')", name="ck_radar_runs_trigger"),
        CheckConstraint("status IN ('running','succeeded','partial','failed')", name="ck_radar_runs_status"),
        Index(
            "ix_radar_runs_org_date_succeeded_unique",
            "organization_id",
            "radar_date",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
        ),
        Index("ix_radar_runs_org_started", "organization_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    radar_date: Mapped[date] = mapped_column(Date, nullable=False)
    trigger: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="running")
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    listed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    detailed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class ApiQuotaUsage(Base):
    __tablename__ = "api_quota_usage"

    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    quota_date: Mapped[date] = mapped_column(Date, primary_key=True)
    requests_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class ApiCallLog(Base):
    __tablename__ = "api_call_log"
    __table_args__ = (
        Index("ix_api_call_log_credential_called", "credential_id", "called_at"),
        Index("ix_api_call_log_radar_run", "radar_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    radar_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    endpoint_name: Mapped[str] = mapped_column(String, nullable=False)
    params_sanitized: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    called_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


__all__ = ["RadarRun", "ApiQuotaUsage", "ApiCallLog"]
