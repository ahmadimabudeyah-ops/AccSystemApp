"""Projects/budgets/audit/dimensions models (Phases 3, 12)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, DateTime, Boolean, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin, SoftDeleteLite,
    SoftDeleteLite,
)


class Project(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "projects"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"))
    budget_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class ProjectCost(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "project_costs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    cost_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))


class ProjectRevenue(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "project_revenues"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    revenue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Budget(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "budgets"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    fiscal_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    approved_by: Mapped[uuid.UUID | None]


class BudgetLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "budget_lines"
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    planned_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)


class AuditLog(Base, PKMixin, TenantMixin):
    """سجل تدقيق إلحاقي — بلا تحديث/حذف | Append-only."""
    __tablename__ = "audit_logs"
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None]
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class Dimension(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "dimensions"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    dim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DimensionValue(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "dimension_values"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    dimension_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    value_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dimension_values.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
