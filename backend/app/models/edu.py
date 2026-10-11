"""Education models (Phase 11)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin, SoftDeleteLite,
)


class Student(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "students"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"))
    student_no: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[str | None] = mapped_column(String(50))
    section_name: Mapped[str | None] = mapped_column(String(50))
    academic_year: Mapped[str] = mapped_column(String(20), default="2026", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class Guardian(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "guardians"
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"))
    full_name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    is_financially_responsible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FeeContract(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "fee_contracts"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    total_fees: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    net_fees: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    installments: Mapped[list["FeeInstallment"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class FeeInstallment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "fee_installments"
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_contracts.id", ondelete="CASCADE"), nullable=False)
    installment_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    contract: Mapped["FeeContract"] = relationship(back_populates="installments")


class FeePayment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "fee_payments"
    installment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_installments.id", ondelete="RESTRICT"), nullable=False)
    pay_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    pay_method: Mapped[str] = mapped_column(String(20), default="cash", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
