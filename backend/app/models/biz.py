"""FX models: daily rates + approval rules + schedules + feedback + portal tokens."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin,
    SoftDeleteLite,
)


class ExchangeRate(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "exchange_rates"
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(18, 10), nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)


class ApprovalRule(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "approval_rules"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    min_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    required_role: Mapped[str] = mapped_column(String(50), nullable=False)
    levels: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReportSchedule(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "report_schedules"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cron: Mapped[str] = mapped_column(String(50), default="0 7 * * *", nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    recipients: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_run_at: Mapped[datetime.datetime | None]
    next_run_at: Mapped[datetime.datetime | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Feedback(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "feedback"
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(30), default="suggestion", nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)


class PortalToken(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "portal_tokens"
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    scope: Mapped[str] = mapped_column(String(30), default="statement", nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    last_used_at: Mapped[datetime.datetime | None]
