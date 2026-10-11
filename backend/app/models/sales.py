"""Sales models (Phase 7 tables)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite,
)


class CustomerInvoice(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_invoices"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    invoice_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    payment_term_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_terms.id", ondelete="RESTRICT"))
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    discount_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    einvoice_uuid: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["CustomerInvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class CustomerInvoiceLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_invoice_lines"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_invoices.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uoms.id", ondelete="RESTRICT"))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_id: Mapped[uuid.UUID | None]
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    invoice: Mapped["CustomerInvoice"] = relationship(back_populates="lines")


class CustomerInvoiceTax(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_invoice_taxes"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_invoices.id", ondelete="CASCADE"), nullable=False)
    line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_invoice_lines.id", ondelete="CASCADE"))
    tax_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)


class CustomerPayment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_payments"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    pay_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    pay_method: Mapped[str] = mapped_column(String(20), default="cash", nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    unallocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(100))
    check_no: Mapped[str | None] = mapped_column(String(50))


class PaymentAllocation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "payment_allocations"
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_payments.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_invoices.id", ondelete="CASCADE"), nullable=False)
    allocated_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    allocated_by: Mapped[uuid.UUID | None]


class PaymentTerm(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "payment_terms"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    term_type: Mapped[str] = mapped_column(String(20), default="net", nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CreditNote(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "credit_notes"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_invoices.id", ondelete="RESTRICT"))
    note_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list["CreditNoteLine"]] = relationship(back_populates="note", cascade="all, delete-orphan")


class CreditNoteLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "credit_note_lines"
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("credit_notes.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    qty: Mapped[float] = mapped_column(Numeric(18, 6), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_id: Mapped[uuid.UUID | None]
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    note: Mapped["CreditNote"] = relationship(back_populates="lines")


class CustomerReturn(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_returns"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_invoices.id", ondelete="RESTRICT"))
    return_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list["CustomerReturnLine"]] = relationship(back_populates="return_", cascade="all, delete-orphan")


class CustomerReturnLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "customer_return_lines"
    return_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_returns.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    returned_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uoms.id", ondelete="RESTRICT"))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_id: Mapped[uuid.UUID | None]
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    condition: Mapped[str] = mapped_column(String(20), default="good", nullable=False)
    return_: Mapped["CustomerReturn"] = relationship(back_populates="lines")
