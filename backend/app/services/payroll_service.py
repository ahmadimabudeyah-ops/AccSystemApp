"""Payroll service (Jordan): SS 7.5/14.25 + progressive income tax from brackets.

Constants SS_* match Social Security Law; ANNUAL_EXEMPTION and brackets live
in income_tax_brackets (seeded, adjustable without code changes).
"""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.hr import (
    SS_EMPLOYEE, SS_EMPLOYER, Employee, IncomeTaxBracket,
    PayrollRun, Payslip, PayslipLine, EmployeeLoan,
)
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, ValidationError, AccountingError

log = logging.getLogger(__name__)
ANNUAL_EXEMPTION = 9000.0


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def annual_tax(annual_taxable: float, year: int, tenant_id) -> float:
    base = max(0.0, annual_taxable - ANNUAL_EXEMPTION)
    brackets = (db.session.query(IncomeTaxBracket)
                .filter_by(tenant_id=tenant_id, year=year, is_deleted=False)
                .order_by(IncomeTaxBracket.from_amount).all())
    tax = 0.0
    for b in brackets:
        lo, hi = float(b.from_amount), (float(b.to_amount) if b.to_amount else None)
        if base <= lo:
            break
        taxable = min(base, hi) - lo if hi else base - lo
        tax += taxable * float(b.rate) / 100
    return round(tax, 3)


def compute_slip(employee: Employee, *, year: int) -> dict:
    """القانون الأردني: الضمان على الأساسي + السكن (المواصلات والإضافي المتغير خارج الوعاء)."""
    ss_base = float(employee.basic_salary) + float(employee.housing_allowance)
    gross = ss_base + float(employee.transport_allowance) + float(employee.other_allowances)
    ss_e = round(ss_base * SS_EMPLOYEE, 3)
    ss_r = round(ss_base * SS_EMPLOYER, 3)
    taxable_monthly = gross - ss_e
    monthly_tax = round(annual_tax(taxable_monthly * 12, year, employee.tenant_id) / 12, 3)
    loan_ded = 0.0
    loan = (db.session.query(EmployeeLoan)
            .filter_by(employee_id=employee.id, status="active", is_deleted=False).first())
    if loan and float(loan.remaining) > 0:
        loan_ded = min(float(loan.installment), float(loan.remaining))
    net = round(gross - ss_e - monthly_tax - loan_ded, 3)
    return {"gross": gross, "ss_employee": ss_e, "ss_employer": ss_r,
            "income_tax": monthly_tax, "loan": loan_ded, "loan_id": loan.id if loan else None,
            "net": net}


def create_run(*, tenant_id, entity_id, fiscal_period_id, pay_month: date,
               employee_ids: list | None = None, actor_id) -> PayrollRun:
    tenant_id = uuid.UUID(str(tenant_id))
    entity_id = uuid.UUID(str(entity_id))
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="payroll", year=pay_month.year)
    run = PayrollRun(tenant_id=tenant_id, entity_id=entity_id,
                     fiscal_period_id=uuid.UUID(str(fiscal_period_id)),
                     run_code=number, pay_month=pay_month.replace(day=1),
                     status="draft", created_by=actor_id, updated_by=actor_id)
    db.session.add(run)
    db.session.flush()
    q = db.session.query(Employee).filter_by(tenant_id=tenant_id, entity_id=entity_id,
                                             status="active", is_deleted=False)
    if employee_ids:
        q = q.filter(Employee.id.in_([uuid.UUID(str(x)) for x in employee_ids]))
    tot = {"gross": 0.0, "ss_e": 0.0, "ss_r": 0.0, "tax": 0.0, "net": 0.0}
    for emp in q.all():
        slip = compute_slip(emp, year=pay_month.year)
        ps = Payslip(tenant_id=tenant_id, run_id=run.id, employee_id=emp.id,
                     gross=slip["gross"], ss_employee=slip["ss_employee"],
                     ss_employer=slip["ss_employer"], income_tax=slip["income_tax"],
                     deductions=slip["loan"], net=slip["net"], status="draft",
                     created_by=actor_id, updated_by=actor_id)
        db.session.add(ps)
        db.session.flush()
        for kind, label, amt in (
                ("earning", "الراتب الإجمالي", slip["gross"]),
                ("deduction", "الضمان — حصة الموظف", slip["ss_employee"]),
                ("deduction", "ضريبة الدخل", slip["income_tax"]),
                ("deduction", "قسط سلفة", slip["loan"]),
                ("employer_cost", "الضمان — حصة الشركة", slip["ss_employer"])):
            if amt:
                db.session.add(PayslipLine(tenant_id=tenant_id, payslip_id=ps.id,
                                           line_type=kind, label_ar=label, amount=amt,
                                           created_by=actor_id, updated_by=actor_id))
        for k, sk in (("gross", "gross"), ("ss_e", "ss_employee"), ("ss_r", "ss_employer"),
                      ("tax", "income_tax"), ("net", "net")):
            tot[k] += slip[sk]
    run.total_gross, run.total_ss_employee, run.total_ss_employer = tot["gross"], tot["ss_e"], tot["ss_r"]
    run.total_tax, run.total_net = tot["tax"], tot["net"]
    db.session.commit()
    return run


def post_run(run_id: uuid.UUID, *, actor_id, salary_expense_code="5110",
             ss_expense_code="5111", salaries_payable_code="2150",
             ss_payable_code="2151", tax_payable_code="2160",
             journal_code: str = "GEN") -> PayrollRun:
    run = db.session.get(PayrollRun, run_id)
    if run is None or run.is_deleted:
        raise NotFoundError("Payroll run not found")
    if run.status == "posted":
        return run
    if run.status != "draft":
        raise BadStateError(f"Cannot post from {run.status}")
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=run.tenant_id, entity_id=run.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    acc = lambda code: _account(run.entity_id, code).id  # noqa: E731
    entry = posting_service.create_entry(
        {"tenant_id": run.tenant_id, "entity_id": run.entity_id, "journal_id": journal.id,
         "entry_type": "payroll", "document_date": run.pay_month, "posting_date": run.pay_month,
         "description": f"رواتب {run.run_code}", "source_module": "payroll",
         "source_document_id": run.id, "source_event_key": f"payroll.run.{run.id}.v1"},
        [{"account_id": acc(salary_expense_code), "debit": float(run.total_gross), "credit": 0},
         {"account_id": acc(ss_expense_code), "debit": float(run.total_ss_employer), "credit": 0},
         {"account_id": acc(salaries_payable_code), "debit": 0, "credit": float(run.total_net)},
         {"account_id": acc(ss_payable_code), "debit": 0,
          "credit": float(run.total_ss_employee) + float(run.total_ss_employer)},
         {"account_id": acc(tax_payable_code), "debit": 0, "credit": float(run.total_tax)}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    run.journal_entry_id = entry.id
    run.event_key = entry.source_event_key
    run.status = "posted"
    for ps in db.session.query(Payslip).filter_by(run_id=run.id).all():
        ps.status = "posted"
    for loan in db.session.query(EmployeeLoan).filter_by(status="active", is_deleted=False).all():
        if loan.employee_id in [p.employee_id for p in
                                db.session.query(Payslip).filter_by(run_id=run.id).all()]:
            pass
    db.session.commit()
    from . import audit_service as _audit_svc
    _audit_svc.record(tenant_id=run.tenant_id, actor_id=actor_id, action="post",
                      entity_type="payroll_runs", entity_id=run.id,
                      new={"run_code": run.run_code, "net": float(run.total_net)})
    db.session.commit()
    return run
