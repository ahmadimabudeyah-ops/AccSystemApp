"""Operations models: tax returns, bank statements, vendor returns, recurring, notifications."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, DateTime, Boolean, Integer, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite,
)


class TaxReturn(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "tax_returns"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    tax_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False)
    period_code: Mapped[str] = mapped_column(String(20), nullable=False)
    sales_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_due: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    filed_at: Mapped[datetime.datetime | None]
    filed_by: Mapped[uuid.UUID | None]


class BankStatement(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "bank_statements"
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False)
    stmt_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    closing_balance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    lines: Mapped[list["BankStatementLine"]] = relationship(back_populates="statement", cascade="all, delete-orphan")


class BankStatementLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "bank_statement_lines"
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False)
    txn_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    is_matched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    matched_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    statement: Mapped["BankStatement"] = relationship(back_populates="lines")


class VendorReturn(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_returns"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    bill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendor_bills.id", ondelete="RESTRICT"))
    return_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    total_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    lines: Mapped[list["VendorReturnLine"]] = relationship(back_populates="return_", cascade="all, delete-orphan")


class VendorReturnLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_return_lines"
    return_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendor_returns.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    returned_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    return_: Mapped["VendorReturn"] = relationship(back_populates="lines")


class RecurringEntry(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "recurring_entries"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journals.id", ondelete="RESTRICT"), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    next_run_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    last_run_on: Mapped[datetime.date | None] = mapped_column(Date)
    template: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Notification(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500))


class PasswordResetToken(Base, PKMixin):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime.datetime | None]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
