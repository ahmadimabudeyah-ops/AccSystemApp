"""Add-on models for round-3 modules (all tables in fix_missing_modules.sql).

Global reference tables (Country/City) carry no tenant_id, mirroring plans/permissions.
Everything else is tenant-scoped with RLS enforced in SQL.
"""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Text, Date, DateTime, Integer, Boolean, BigInteger,
    ForeignKey, Numeric, CHAR,
)
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin,
    SoftDeleteMixin, SoftDeleteLite,
)


# ------------------------------------------------------------- global reference

class Country(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "countries"
    code: Mapped[str] = mapped_column(CHAR(2), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)


class City(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "cities"
    country_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("countries.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)


# ------------------------------------------------------------- purchases

class PurchaseAgreement(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "purchase_agreements"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    start_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    lines: Mapped[list["PurchaseAgreementLine"]] = relationship(back_populates="agreement", cascade="all, delete-orphan")


class PurchaseAgreementLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "purchase_agreement_lines"
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_agreements.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    agreement: Mapped["PurchaseAgreement"] = relationship(back_populates="lines")


# ------------------------------------------------------------- sales debit notes

class DebitNote(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "debit_notes"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    note_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    currency_id: Mapped[str] = mapped_column(CHAR(3), default="JOD", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    event_key: Mapped[str | None] = mapped_column(String(200))
    lines: Mapped[list["DebitNoteLine"]] = relationship(back_populates="note", cascade="all, delete-orphan")


class DebitNoteLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "debit_note_lines"
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("debit_notes.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    qty: Mapped[float] = mapped_column(Numeric(18, 6), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    tax_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"))
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    note: Mapped["DebitNote"] = relationship(back_populates="lines")


# ------------------------------------------------------------- treasury

class BankReconciliation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "bank_reconciliations"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    statement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statements.id", ondelete="RESTRICT"), nullable=False)
    reconciled_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lines: Mapped[list["BankReconciliationLine"]] = relationship(back_populates="reconciliation", cascade="all, delete-orphan")


class BankReconciliationLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "bank_reconciliation_lines"
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_reconciliations.id", ondelete="CASCADE"), nullable=False)
    statement_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statement_lines.id", ondelete="RESTRICT"), nullable=False)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    reconciliation: Mapped["BankReconciliation"] = relationship(back_populates="lines")


class CheckBook(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "check_books"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    start_no: Mapped[str] = mapped_column(String(50), nullable=False)
    end_no: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


# ------------------------------------------------------------- assets

class AssetTransfer(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "asset_transfers"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    transfer_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    from_text: Mapped[str | None] = mapped_column(String(200))
    to_text: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="posted", nullable=False)


class AssetDisposal(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "asset_disposals"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    disposal_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    proceeds: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    gain_loss: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="posted", nullable=False)


class AssetRevaluation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "asset_revaluations"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    reval_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    old_cost: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    new_cost: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="posted", nullable=False)


class AssetDepreciationSchedule(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "asset_depreciation_schedules"
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)


# ------------------------------------------------------------- finance

class Loan(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "loans"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    lender: Mapped[str] = mapped_column(String(200), nullable=False)
    principal: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    annual_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    start_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    schedules: Mapped[list["LoanSchedule"]] = relationship(back_populates="loan", cascade="all, delete-orphan")


class LoanSchedule(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "loan_schedules"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    payment: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    principal_part: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    interest_part: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    remaining: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    loan: Mapped["Loan"] = relationship(back_populates="schedules")


class LoanTransaction(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "loan_transactions"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    txn_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))


# ------------------------------------------------------------- taxes

class TaxGroup(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "tax_groups"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TaxRate(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "tax_rates"
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tax_groups.id", ondelete="CASCADE"), nullable=False)
    tax_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False)
    valid_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[datetime.date | None] = mapped_column(Date)


class TaxPayment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "tax_payments"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    tax_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False)
    pay_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    period_code: Mapped[str | None] = mapped_column(String(20))
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


class WithholdingTax(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "withholding_taxes"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    base_amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    doc_ref: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


# ------------------------------------------------------------- payroll

class EmployeeContract(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "employee_contracts"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    start_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_on: Mapped[datetime.date | None] = mapped_column(Date)
    basic_salary: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class SalaryStructure(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "salary_structures"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lines: Mapped[list["SalaryStructureLine"]] = relationship(back_populates="structure", cascade="all, delete-orphan")


class SalaryStructureLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "salary_structure_lines"
    structure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="earning", nullable=False)
    formula: Mapped[str] = mapped_column(String(200), default="fixed", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    structure: Mapped["SalaryStructure"] = relationship(back_populates="lines")


class LeaveType(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "leave_types"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    annual_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeaveBalance(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "leave_balances"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    entitled: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    used: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)


class AttendanceRecord(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "attendance_records"
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="present", nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 2), default=8, nullable=False)


# ------------------------------------------------------------- education

class AcademicYear(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "academic_years"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    terms: Mapped[list["AcademicTerm"]] = relationship(back_populates="year", cascade="all, delete-orphan")


class AcademicTerm(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "academic_terms"
    year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    year: Mapped["AcademicYear"] = relationship(back_populates="terms")


class GradeLevel(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "grade_levels"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FeeStructure(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "fee_structures"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), default="2026", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    lines: Mapped[list["FeeStructureLine"]] = relationship(back_populates="structure", cascade="all, delete-orphan")


class FeeStructureLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "fee_structure_lines"
    structure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False)
    grade_code: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    structure: Mapped["FeeStructure"] = relationship(back_populates="lines")


# ------------------------------------------------------------- projects & budgets

class ProjectPhase(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "project_phases"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_on: Mapped[datetime.date | None] = mapped_column(Date)
    ends_on: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    tasks: Mapped[list["ProjectTask"]] = relationship(back_populates="phase", cascade="all, delete-orphan")


class ProjectTask(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "project_tasks"
    phase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_phases.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_cost: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    progress_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    phase: Mapped["ProjectPhase"] = relationship(back_populates="tasks")


class BudgetVersion(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "budget_versions"
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


class BudgetTransfer(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "budget_transfers"
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False)
    from_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    to_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


class Forecast(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "forecasts"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    lines: Mapped[list["ForecastLine"]] = relationship(back_populates="forecast", cascade="all, delete-orphan")


class ForecastLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "forecast_lines"
    forecast_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    month: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    forecast: Mapped["Forecast"] = relationship(back_populates="lines")


# ------------------------------------------------------------- integrations

class Integration(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "integrations"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), default="webhook", nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Webhook(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "webhooks"
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WebhookDelivery(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "webhook_deliveries"
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class ApiRequestLog(Base, PKMixin, TimestampMixin, VersionMixin, SoftDeleteLite):
    """سجل طلبات API — tenant_id اختياري (قد تكون الطلبات مجهولة المستأجر)."""
    __tablename__ = "api_request_logs"
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    actor_id: Mapped[uuid.UUID | None]


# ------------------------------------------------------------- attachments

class Attachment(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "attachments"
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(128))
    linked_type: Mapped[str | None] = mapped_column(String(100))
    linked_id: Mapped[uuid.UUID | None]


class DocumentTemplate(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "document_templates"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), default="invoice", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ------------------------------------------------------------- security

class Delegation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "delegations"
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    scope: Mapped[str] = mapped_column(String(200), default="all", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApiKey(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "api_keys"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    expires_on: Mapped[datetime.date | None] = mapped_column(Date)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
