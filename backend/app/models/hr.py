"""Payroll models (Phase 10, Jordan)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin, SoftDeleteLite,
)

SS_EMPLOYEE = 0.075
SS_EMPLOYER = 0.1425


class Employee(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "employees"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"))
    employee_no: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    national_id: Mapped[str | None] = mapped_column(String(20))
    ss_number: Mapped[str | None] = mapped_column(String(30))
    hire_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    basic_salary: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    housing_allowance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    transport_allowance: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    other_allowances: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    bank_iban: Mapped[str | None] = mapped_column(String(34))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class IncomeTaxBracket(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "income_tax_brackets"
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    from_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    to_amount: Mapped[float | None] = mapped_column(Numeric(18, 3))
    rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PayrollRun(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "payroll_runs"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)
    run_code: Mapped[str] = mapped_column(String(50), nullable=False)
    pay_month: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_gross: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    total_ss_employee: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    total_ss_employer: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    total_tax: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    total_net: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))


class Payslip(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "payslips"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    gross: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    ss_employee: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    ss_employer: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    income_tax: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    deductions: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    net: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


class PayslipLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "payslip_lines"
    payslip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payslips.id", ondelete="CASCADE"), nullable=False)
    line_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)


class EmployeeLoan(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "employee_loans"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    installment: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    remaining: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class LeaveRequest(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "leave_requests"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(30), default="annual", nullable=False)
    from_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    to_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
