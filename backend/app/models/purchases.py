"""Purchases models (Phase 9)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, DateTime, Integer, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite,
)


class VendorBill(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_bills"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    bill_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    supplier_ref: Mapped[str | None] = mapped_column(String(100))
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list["VendorBillLine"]] = relationship(back_populates="bill", cascade="all, delete-orphan")


class VendorBillLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_bill_lines"
    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendor_bills.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    bill: Mapped["VendorBill"] = relationship(back_populates="lines")


class VendorPayment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_payments"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    pay_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    pay_method: Mapped[str] = mapped_column(String(20), default="bank_transfer", nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    unallocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))


class VendorPaymentAllocation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "vendor_payment_allocations"
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendor_payments.id", ondelete="CASCADE"), nullable=False)
    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendor_bills.id", ondelete="CASCADE"), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    allocated_by: Mapped[uuid.UUID | None]


class BillMatch(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    """سجل المطابقة الثلاثية المعتمدة لفاتورة مورد."""
    __tablename__ = "bill_matches"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendor_bills.id", ondelete="RESTRICT"), nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[dict | list] = mapped_column(JSONB, default=list, nullable=False)
    matched_by: Mapped[uuid.UUID | None]
    matched_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))