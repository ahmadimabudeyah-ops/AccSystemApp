"""Tenant + subscription models (Phase 1, group A)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, Numeric, Boolean, ForeignKey
from .base import Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin


class Tenant(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "tenants"
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Amman", nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(2), default="JO", nullable=False)


class Plan(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    max_entities: Mapped[int] = mapped_column(default=1, nullable=False)
    max_users: Mapped[int] = mapped_column(default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subscription(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "subscriptions"
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="trial", nullable=False)
