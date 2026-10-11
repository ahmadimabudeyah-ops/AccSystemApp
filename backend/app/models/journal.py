"""Accounting engine models: journals, entries, lines, idempotency, reversal, approvals.

COMMENT ON TABLE journal_entries IS 'القيود — المرحل لا يعدل | Entries immutable when posted';
COMMENT ON TABLE event_keys IS 'منع الازدواج | Idempotency keys';
"""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, DateTime, Boolean, Integer, BigInteger, ForeignKey, Numeric, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin,
)

ENTRY_TYPES = (
    "manual", "source", "opening", "reversal", "closing", "adjustment",
    "accrual", "deferral", "revaluation", "consolidation", "payroll", "inventory", "depreciation",
)
ENTRY_STATUSES = ("draft", "pending_review", "approved", "posted", "reversed", "cancelled", "rejected")
JOURNAL_TYPES = (
    "sale", "purchase", "cash", "bank", "general", "opening", "closing",
    "adjustment", "revaluation", "consolidation", "payroll", "inventory", "asset",
)


class Journal(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """دفاتر اليومية | Journals."""

    __tablename__ = "journals"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column("name_ar", String(255), nullable=False)
    type: Mapped[str] = mapped_column("journal_type", String(30), default="general", nullable=False)
    currency_id: Mapped[str] = mapped_column("default_currency", String(3), default="JOD", nullable=False)
    default_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    sequence_prefix: Mapped[str] = mapped_column("prefix", String(20), default="", nullable=False)
    sequence_length: Mapped[int] = mapped_column("number_length", Integer, default=6, nullable=False)
    requires_approval: Mapped[bool] = mapped_column("require_approval", Boolean, default=True, nullable=False)
    allow_manual: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "code", name="uq_journals_code"),)


class JournalSequence(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """تسلسل أرقام القيود لكل دفتر/سنة | Per-journal-year sequences."""

    __tablename__ = "journal_sequences"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    journal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journals.id", ondelete="CASCADE"), nullable=False)
    fiscal_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False)
    last_number: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    suffix: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    length: Mapped[int] = mapped_column("number_length", Integer, default=6, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "journal_id", "fiscal_year_id", name="uq_jseq"),)


class JournalEntry(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """رأس القيد | Journal entry header."""

    __tablename__ = "journal_entries"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)
    journal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journals.id", ondelete="RESTRICT"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    document_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    period_id: Mapped[uuid.UUID] = mapped_column("fiscal_period_id", ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(String(100))
    source_module: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    source_document_id: Mapped[uuid.UUID | None]
    source_event_key: Mapped[str | None] = mapped_column("event_key", String(200))
    source_version: Mapped[int] = mapped_column("event_version", Integer, default=1, nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    total_debit: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    total_credit: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    status_changed_at: Mapped[datetime.datetime | None]
    status_changed_by: Mapped[uuid.UUID | None]
    official_number: Mapped[str | None] = mapped_column(String(60), index=True)
    approved_at: Mapped[datetime.datetime | None]
    approved_by: Mapped[uuid.UUID | None]
    posted_at: Mapped[datetime.datetime | None]
    posted_by: Mapped[uuid.UUID | None]
    reversed_at: Mapped[datetime.datetime | None]
    reversed_by: Mapped[uuid.UUID | None]
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"), index=True)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", "journal_id", "official_number", name="uq_entry_official"),
        UniqueConstraint("tenant_id", "entity_id", "event_key", name="uq_entry_event"),
        Index("ix_entries_entity_status", "entity_id", "status"),
    )


class JournalLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """سطر القيد — جهة واحدة فقط (مدين XOR دائن) | One side per line."""

    __tablename__ = "journal_lines"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    credit: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    amount_currency: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    amount_functional: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    partner_id: Mapped[uuid.UUID | None]
    due_date: Mapped[datetime.date | None] = mapped_column("due_on", Date)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    dimensions: Mapped[dict] = mapped_column("dims", JSONB, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_line_ref: Mapped[str | None] = mapped_column(String(100))
    reconciliation_id: Mapped[uuid.UUID | None] = mapped_column("recon_id")
    reconciled_at: Mapped[datetime.datetime | None] = mapped_column("recon_at")
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settled_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")

    __table_args__ = (UniqueConstraint("entry_id", "line_number", name="uq_line_no"),)


class EventKey(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """مفاتيح الأحداث لمنع الازدواج | Idempotency registry."""

    __tablename__ = "event_keys"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    source_module: Mapped[str] = mapped_column(String(50), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column("process_status", String(20), default="pending", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column("resulting_entry_id", ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    processed_at: Mapped[datetime.datetime | None]
    retry_count: Mapped[int] = mapped_column("attempts", Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    # NOTE: attribute named `extra` — `metadata` is reserved by DeclarativeBase
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "event_key", name="uq_event_key"),)


class ReversalLink(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """روابط العكس — عكس كامل واحد للأصل | One full reversal per entry."""

    __tablename__ = "reversal_links"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    original_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, unique=True)
    reversal_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, unique=True)
    reversal_date: Mapped[datetime.datetime | None] = mapped_column("reversed_at", DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reversed_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reversal_type: Mapped[str] = mapped_column(String(20), default="full", nullable=False)
    amount_reversed: Mapped[float | None] = mapped_column("reversed_amount", Numeric(18, 3))
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)


class EntryApproval(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """اعتمادات القيود | Entry approvals (maker != checker)."""

    __tablename__ = "entry_approvals"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(20), default="final", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime.datetime | None] = mapped_column("decided_at")
    sequence: Mapped[int] = mapped_column("seq", Integer, default=1, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sla_due_at: Mapped[datetime.datetime | None] = mapped_column("sla_due_at")
    notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime.datetime | None]


class EntryAttachment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """مرفقات القيود (الملف في تخزين خارجي) | Attachments (file in external storage)."""

    __tablename__ = "entry_attachments"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow, nullable=False)


class EntryComment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    """تعليقات القيود — لا تغير القيد | Comments never mutate the entry."""

    __tablename__ = "entry_comments"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    comment: Mapped[str] = mapped_column("comment_text", Text, nullable=False)
    commented_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    commented_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(30), default="note", nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
