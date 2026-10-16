"""Treasury + currencies + taxes models (Phase 8)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, Boolean, Integer, BigInteger, ForeignKey, Numeric
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin,
)


class Currency(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "currencies"
    code: Mapped[str] = mapped_column(String(3), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    decimals: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Tax(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "taxes"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(30), default="sale", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashBox(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "cash_boxes"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashTransaction(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "cash_transactions"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    box_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cash_boxes.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)
    txn_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    party_id: Mapped[uuid.UUID | None]
    description: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="posted", nullable=False)


class Bank(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "banks"
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankAccount(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "bank_accounts"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(34))
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Check(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "checks"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False)
    check_no: Mapped[str] = mapped_column(String(50), nullable=False)
    payee: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="issued", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    reversal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))


class Transfer(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "transfers"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    from_box_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_boxes.id", ondelete="RESTRICT"))
    to_box_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_boxes.id", ondelete="RESTRICT"))
    from_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id", ondelete="RESTRICT"))
    to_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id", ondelete="RESTRICT"))
    transfer_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="posted", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))


class DocSequence(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """تسلسل أرقام المستندات | Document numbering."""
    __tablename__ = "doc_sequences"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doctype: Mapped[str] = mapped_column(String(30), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_number: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
