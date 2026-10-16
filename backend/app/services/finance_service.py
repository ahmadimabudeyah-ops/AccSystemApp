"""Finance service: loans (amortization schedules, disbursement, repayments)."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from ..extensions import db
from ..models.addons import Loan, LoanSchedule, LoanTransaction
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, ValidationError

log = logging.getLogger(__name__)


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def create_loan(*, tenant_id, entity_id, lender, principal, annual_rate=0,
                start_on=None, months, actor_id) -> Loan:
    tenant_id = uuid.UUID(str(tenant_id))
    entity_id = uuid.UUID(str(entity_id))
    start_on = start_on or date.today()
    if float(principal) <= 0 or int(months) <= 0:
        raise ValidationError("principal and months must be > 0")
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="loan", year=start_on.year)
    loan = Loan(tenant_id=tenant_id, entity_id=entity_id, code=number, lender=lender,
                principal=principal, annual_rate=annual_rate or 0,
                start_on=start_on, months=int(months), status="active",
                created_by=actor_id, updated_by=actor_id)
    db.session.add(loan)
    db.session.flush()
    _build_schedule(loan, actor_id=actor_id)
    db.session.commit()
    return loan


def _build_schedule(loan: Loan, *, actor_id) -> None:
    principal = Decimal(str(loan.principal))
    r = Decimal(str(loan.annual_rate or 0)) / 100 / 12
    n = int(loan.months)
    if r > 0:
        pmt = (principal * r / (1 - (1 + r) ** (-n))).quantize(Decimal("0.001"))
    else:
        pmt = (principal / n).quantize(Decimal("0.001"))
    remaining = principal
    for i in range(1, n + 1):
        interest = (remaining * r).quantize(Decimal("0.001")) if r > 0 else Decimal("0")
        princ = min(pmt - interest, remaining)
        if i == n:
            princ = remaining
            pmt = princ + interest
        remaining -= princ
        db.session.add(LoanSchedule(
            tenant_id=loan.tenant_id, loan_id=loan.id, period_no=i,
            due_on=loan.start_on + relativedelta(months=i - 1),
            payment=pmt, principal_part=princ, interest_part=interest,
            remaining=max(remaining, Decimal("0")),
            created_by=actor_id, updated_by=actor_id))


def post_disbursement(loan_id: uuid.UUID, *, cash_account_id, liability_code="2010",
                      journal_code: str = "BANK", actor_id) -> LoanTransaction:
    """صرف القرض: نقدية مدينة / التزام دائن."""
    loan = db.session.get(Loan, loan_id)
    if loan is None or loan.is_deleted:
        raise NotFoundError("Loan not found")
    if loan.status != "active":
        raise BadStateError(f"Cannot disburse from {loan.status}")
    if db.session.query(LoanTransaction).filter_by(
            loan_id=loan.id, kind="disbursement", is_deleted=False).first():
        raise BadStateError("Already disbursed")
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=loan.tenant_id, entity_id=loan.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    liab = _account(loan.entity_id, liability_code)
    entry = posting_service.create_entry(
        {"tenant_id": loan.tenant_id, "entity_id": loan.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": loan.start_on, "posting_date": loan.start_on,
         "description": f"صرف قرض {loan.code}", "source_module": "finance",
         "source_document_id": loan.id, "source_event_key": f"finance.loan.{loan.id}.disburse.v1",
         "currency_id": "JOD", "exchange_rate": 1},
        [{"account_id": uuid.UUID(str(cash_account_id)), "debit": float(loan.principal), "credit": 0},
         {"account_id": liab.id, "debit": 0, "credit": float(loan.principal)}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    txn = LoanTransaction(tenant_id=loan.tenant_id, loan_id=loan.id, txn_date=loan.start_on,
                          kind="disbursement", amount=float(loan.principal),
                          journal_entry_id=entry.id, created_by=actor_id, updated_by=actor_id)
    db.session.add(txn)
    db.session.commit()
    return txn


def post_repayment(schedule_id: uuid.UUID, *, cash_account_id, liability_code="2010",
                   interest_account_code="5160", journal_code: str = "BANK", actor_id) -> LoanSchedule:
    """سداد قسط: التزام + فائدة مدينة / نقدية دائنة."""
    sched = db.session.get(LoanSchedule, schedule_id)
    if sched is None or sched.is_deleted:
        raise NotFoundError("Schedule line not found")
    if sched.status == "paid":
        return sched
    if sched.status != "pending":
        raise BadStateError(f"Cannot pay from {sched.status}")
    loan = db.session.get(Loan, sched.loan_id)
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=loan.tenant_id, entity_id=loan.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    liab = _account(loan.entity_id, liability_code)
    interest_acc = _account(loan.entity_id, interest_account_code)
    entry = posting_service.create_entry(
        {"tenant_id": loan.tenant_id, "entity_id": loan.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": sched.due_on, "posting_date": sched.due_on,
         "description": f"سداد قسط {loan.code}/{sched.period_no}", "source_module": "finance",
         "source_document_id": sched.id, "source_event_key": f"finance.loan.{sched.id}.pay.v1",
         "currency_id": "JOD", "exchange_rate": 1},
        [{"account_id": liab.id, "debit": float(sched.principal_part), "credit": 0},
         {"account_id": interest_acc.id, "debit": float(sched.interest_part), "credit": 0},
         {"account_id": uuid.UUID(str(cash_account_id)), "debit": 0, "credit": float(sched.payment)}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    sched.entry_id = entry.id
    sched.status = "paid"
    db.session.add(LoanTransaction(tenant_id=loan.tenant_id, loan_id=loan.id, txn_date=sched.due_on,
                                   kind="repayment", amount=float(sched.payment),
                                   journal_entry_id=entry.id,
                                   created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return sched
