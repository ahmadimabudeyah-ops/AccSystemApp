"""Education service: fee contracts, installments, collection with posting."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.edu import FeeContract, FeeInstallment, FeePayment
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, ValidationError, AccountingError

log = logging.getLogger(__name__)


def create_contract(*, tenant_id, entity_id, student_id, academic_year,
                    total_fees, discount_pct=0.0, installments: list[dict] | int = 4,
                    actor_id) -> FeeContract:
    tenant_id = uuid.UUID(str(tenant_id))
    net = float(Decimal(str(total_fees)) * (1 - Decimal(str(discount_pct)) / 100))
    c = FeeContract(tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
                    student_id=uuid.UUID(str(student_id)), academic_year=academic_year,
                    total_fees=total_fees, discount_pct=discount_pct, net_fees=net,
                    status="active", created_by=actor_id, updated_by=actor_id)
    db.session.add(c)
    db.session.flush()
    if isinstance(installments, int):
        per = round(net / installments, 3)
        schedule = [{"due_on": date.today(), "amount": per}] * installments
    else:
        schedule = installments
    for i, s in enumerate(schedule, 1):
        db.session.add(FeeInstallment(
            tenant_id=tenant_id, contract_id=c.id, installment_no=i,
            due_on=s["due_on"] if isinstance(s.get("due_on"), date)
            else date.fromisoformat(s["due_on"]),
            amount=s["amount"], status="pending", created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return c


def post_contract(contract_id: uuid.UUID, *, actor_id, revenue_account_code="4020",
                  journal_code: str = "SALE") -> FeeContract:
    """استحقاق الرسوم: ذمم مدينة / إيراد تعليمي."""
    c = db.session.get(FeeContract, contract_id)
    if c is None or c.is_deleted:
        raise NotFoundError("Contract not found")
    if c.journal_entry_id:
        return c
    from ..models.edu import Student
    from ..models.journal import Journal
    from ..models.account import Account
    student = db.session.get(Student, c.student_id)
    party_id = student.party_id if student and student.party_id else None
    if party_id is None:
        raise ValidationError("Student has no linked party for receivables")
    recv = db.session.query(Account).filter_by(entity_id=c.entity_id, code="1210", is_deleted=False).first()
    rev = db.session.query(Account).filter_by(entity_id=c.entity_id, code=revenue_account_code, is_deleted=False).first()
    if recv is None or rev is None:
        raise NotFoundError("Receivable/revenue accounts not configured")
    journal = db.session.query(Journal).filter_by(
        tenant_id=c.tenant_id, entity_id=c.entity_id, code=journal_code, is_deleted=False).first()
    entry = posting_service.create_entry(
        {"tenant_id": c.tenant_id, "entity_id": c.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": date.today(), "posting_date": date.today(),
         "description": f"رسوم {student.student_no}", "source_module": "education",
         "source_document_id": c.id, "source_event_key": f"edu.contract.{c.id}.v1"},
        [{"account_id": recv.id, "debit": float(c.net_fees), "credit": 0, "partner_id": party_id},
         {"account_id": rev.id, "debit": 0, "credit": float(c.net_fees), "partner_id": party_id}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    c.journal_entry_id = entry.id
    c.event_key = entry.source_event_key
    db.session.commit()
    return c


def collect(*, installment_id, amount, pay_method="cash", cash_account_code="101001",
            actor_id) -> FeePayment:
    inst = db.session.get(FeeInstallment, uuid.UUID(str(installment_id)))
    if inst is None or inst.is_deleted:
        raise NotFoundError("Installment not found")
    if float(amount) > float(inst.amount) - float(inst.paid_amount) + 0.001:
        raise ValidationError("Payment exceeds installment remainder")
    from ..models.edu import Student
    from ..models.journal import Journal
    from ..models.account import Account
    contract = db.session.get(FeeContract, inst.contract_id)
    student = db.session.get(Student, contract.student_id)
    cash = db.session.query(Account).filter_by(entity_id=contract.entity_id, code=cash_account_code, is_deleted=False).first()
    recv = db.session.query(Account).filter_by(entity_id=contract.entity_id, code="1210", is_deleted=False).first()
    journal = db.session.query(Journal).filter_by(
        tenant_id=contract.tenant_id, entity_id=contract.entity_id, code="CASH", is_deleted=False).first()
    entry = posting_service.create_entry(
        {"tenant_id": contract.tenant_id, "entity_id": contract.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": date.today(), "posting_date": date.today(),
         "description": f"تحصيل رسوم {student.student_no}", "source_module": "education",
         "source_document_id": inst.id, "source_event_key": f"edu.pay.{inst.id}.{amount}.v1"},
        [{"account_id": cash.id, "debit": float(amount), "credit": 0, "partner_id": student.party_id},
         {"account_id": recv.id, "debit": 0, "credit": float(amount), "partner_id": student.party_id}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    pay = FeePayment(tenant_id=contract.tenant_id, installment_id=inst.id,
                     pay_date=date.today(), amount=amount, pay_method=pay_method,
                     journal_entry_id=entry.id, created_by=actor_id, updated_by=actor_id)
    db.session.add(pay)
    inst.paid_amount = float(inst.paid_amount) + float(amount)
    inst.status = "paid" if inst.paid_amount >= float(inst.amount) - 0.001 else "partially_paid"
    db.session.commit()
    return pay
