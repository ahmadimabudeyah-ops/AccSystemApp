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
    "bank", "cash", "tax", "loan", "equity", "receivable", "payable",
    "prepaid", "accrued",
)
# المستوى الوظيفي في الدليل (تصميم محلي، ليس قاعدة محاسبية عامة).
# NULL = حساب قديم غير مصنف بالمستويات الجديدة (legacy) — لا يُستنتج تخمينًا.
HIERARCHY_ROLES = ("section", "general", "subsidiary", "detail")
# عائلات التصنيف: الحساب المقابل (contra) ينتمي لعائلة أصله.
ACCOUNT_FAMILIES = {
    "asset": "assets", "contra_asset": "assets",
    "liability": "liabilities", "contra_liability": "liabilities",
    "equity": "equity", "contra_equity": "equity",
    "income": "income", "contra_income": "income",
    "expense": "expenses", "contra_expense": "expenses",
}
# الطبيعة المقترحة (عرض/افتراض فقط — ليست قيد ترحيل).
SUGGESTED_BALANCE = {
    "asset": "debit", "expense": "debit",
    "contra_liability": "debit", "contra_equity": "debit", "contra_income": "debit",
    "liability": "credit", "equity": "credit", "income": "credit",
    "contra_asset": "credit", "contra_expense": "credit",
}


class Account(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """دليل الحسابات | Chart of accounts."""

    __tablename__ = "accounts"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), index=True)
    # --- أعمدة موجودة في قاعدة البيانات ولم تكن في ORM ---
    level: Mapped[int] = mapped_column(default=1, nullable=False)
    path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    currency_restriction: Mapped[str | None] = mapped_column(String(3))
    require_dimensions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_dimensions: Mapped[dict | list] = mapped_column(JSONB, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    # المستوى الوظيفي الجديد (NULL = قديم غير مصنف).
    hierarchy_role: Mapped[str | None] = mapped_column(String(20))
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
