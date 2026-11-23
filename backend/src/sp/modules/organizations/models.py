from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Index, Integer, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sp.core.db import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        Index(
            "ix_organizations_rut_unique",
            "rut",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    rut: Mapped[str | None] = mapped_column(String, nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','commercial','reviewer','read_only')",
            name="ck_organization_members_role",
        ),
        Index("ix_organization_members_user_id", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class ApiCredential(Base):
    __tablename__ = "api_credentials"
    __table_args__ = (
        CheckConstraint("daily_limit BETWEEN 1 AND 10000", name="ck_api_credentials_daily_limit"),
        Index(
            "ix_api_credentials_org_provider_active",
            "organization_id",
            "provider",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, server_default="mercado_publico")
    ticket_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    holder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(nullable=True)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8000")
    max_rps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
