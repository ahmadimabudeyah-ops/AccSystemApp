"""Chart of accounts models: Account + AccountHierarchy (closure table).

COMMENT ON TABLE accounts IS 'دليل الحسابات — Chart of accounts';
COMMENT ON COLUMN accounts.code IS 'الرمز (نصي يحفظ الأصفار) | Code keeps leading zeros';
"""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Boolean, ForeignKey, UUID
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin,
)

ACCOUNT_TYPES = (
    "asset", "liability", "equity", "income", "expense",
    "contra_asset", "contra_liability", "contra_equity", "contra_income", "contra_expense",
)
CONTROL_TYPES = (
    "general", "customer", "supplier", "employee", "inventory", "asset",
    "bank", "cash", "tax", "loan", "equity",
)


class Account(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """دليل الحسابات | Chart of accounts."""

    __tablename__ = "accounts"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), index=True)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    control_type: Mapped[str] = mapped_column(String(30), default="general", nullable=False)
    is_postable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False)
    allow_manual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reconcilable: Mapped[bool] = mapped_column("is_reconcilable", Boolean, default=False, nullable=False)
    require_partner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_from: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today, nullable=False)
    valid_to: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    parent: Mapped["Account | None"] = relationship("Account", remote_side="Account.id", back_populates="children")
    children: Mapped[list["Account"]] = relationship("Account", back_populates="parent")

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("tenant_id", "entity_id", "code", name="uq_accounts_code"),
    )


class AccountHierarchy(Base, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """إغلاق الهرمية للاستعلام السريع | Closure table for fast tree queries."""

    __tablename__ = "account_hierarchy"

    ancestor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    descendant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    depth: Mapped[int] = mapped_column(default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
