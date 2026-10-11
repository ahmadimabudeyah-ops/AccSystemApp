"""Purchases service: bills (auto-posting GRNI/stock/expense vs supplier), payments, allocations."""
from __future__ import annotations
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from ..extensions import db
from ..models.purchases import (
    VendorBill, VendorBillLine, VendorPayment, VendorPaymentAllocation,
)
from ..models.product import Product
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, ValidationError, AccountingError

log = logging.getLogger(__name__)


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def create_bill(*, tenant_id, entity_id, supplier_id, bill_date: date,
                payment_term_days: int = 0, currency_id="JOD", exchange_rate=1,
                supplier_ref=None, lines: list[dict], notes=None, actor_id) -> VendorBill:
    tenant_id, entity_id, supplier_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, supplier_id))
    if not lines:
        raise ValidationError("Bill needs at least one line")
    try:
        fx = float(exchange_rate or 1)
    except (TypeError, ValueError):
        fx = 1
    if fx <= 0:
        raise ValidationError("exchange_rate must be > 0")
    from ..models.biz import Tax as _Tax
    sub = Decimal("0")
    tax = Decimal("0")
    enriched = []
    for l in lines:
        net = Decimal(str(l["qty"])) * Decimal(str(l["unit_price"])) * (
            1 - Decimal(str(l.get("discount_pct", 0))) / 100)
        rate = Decimal(str(l.get("tax_rate", 0) or 0))
        if l.get("tax_id"):
            t = db.session.get(_Tax, uuid.UUID(str(l["tax_id"])))
            if t is None or not t.is_active:
                raise ValidationError(f"Invalid tax: {l['tax_id']}")
            rate = Decimal(str(t.rate))
        t_amount = (net * rate / 100).quantize(Decimal("0.001"))
        sub += net
        tax += t_amount
        enriched.append((l, net, t_amount))
    grand = sub + tax
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="bill", year=bill_date.year)
    bill = VendorBill(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                      supplier_id=supplier_id, bill_date=bill_date,
                      due_on=bill_date + timedelta(days=payment_term_days),
                      supplier_ref=supplier_ref, currency_id=currency_id, exchange_rate=fx,
                      subtotal=sub, tax_total=tax, grand_total=grand,
                      paid_amount=0, remaining_amount=grand,
                      status="draft", notes=notes, created_by=actor_id, updated_by=actor_id)
    db.session.add(bill)
    db.session.flush()
    for i, (l, net, t_amount) in enumerate(enriched, 1):
        product = db.session.get(Product, uuid.UUID(str(l["product_id"])))
        if product is None:
            raise ValidationError(f"Unknown product: {l['product_id']}")
        db.session.add(VendorBillLine(
            tenant_id=tenant_id, bill_id=bill.id, line_number=i, product_id=product.id,
            description=l.get("description", product.name_ar), qty=l["qty"],
            unit_price=l["unit_price"], line_total=net + t_amount,
            account_id=uuid.UUID(str(l["account_id"])) if l.get("account_id") else None,
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return bill


def post_bill(bill_id: uuid.UUID, *, actor_id, journal_code: str = "PURCH") -> VendorBill:
    """ترحيل الفاتورة: مخزون/مصروف مدين / مورد دائن."""
    bill = db.session.get(VendorBill, bill_id)
    if bill is None or bill.is_deleted:
        raise NotFoundError("Bill not found")
    if bill.status == "posted":
        return bill
    if bill.status != "draft":
        raise BadStateError(f"Cannot post from {bill.status}")
    from . import approval_service as _appr
    _appr.check_doc_rule(tenant_id=bill.tenant_id, entity_id=bill.entity_id,
                         doc_type="bill", total=float(bill.grand_total),
                         creator_id=bill.created_by, poster_id=actor_id)
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=bill.tenant_id, entity_id=bill.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    supplier_acc = _account(bill.entity_id, "2010")
    stock_default = _account(bill.entity_id, "1310")
    vat = _account(bill.entity_id, "2140")  # ضريبة المدخلات القابلة للاسترداد — مدينة (تخفّض صافي المستحق)
    fx = float(bill.exchange_rate or 1)
    lines = []
    for l in bill.lines:
        if l.is_deleted:
            continue
        acc = l.account_id or stock_default.id
        lines.append({"account_id": acc, "debit": float(l.line_total), "credit": 0,
                      "partner_id": bill.supplier_id})
    if float(bill.tax_total or 0) > 0:
        # سطور البنود مسجلة بالصافي (line_total متضمن الضريبة) في المخزون أعلاه؛
        # نعيد التصنيف: الضريبة مدينة على 2140 مقابل تخفيض المخزون/المصروف.
        lines.append({"account_id": stock_default.id, "debit": 0, "credit": float(bill.tax_total),
                      "partner_id": bill.supplier_id})
        lines.append({"account_id": vat.id, "debit": float(bill.tax_total), "credit": 0,
                      "partner_id": bill.supplier_id})
    lines.append({"account_id": supplier_acc.id, "debit": 0, "credit": float(bill.grand_total),
                  "partner_id": bill.supplier_id})
    entry = posting_service.create_entry(
        {"tenant_id": bill.tenant_id, "entity_id": bill.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": bill.bill_date, "posting_date": bill.bill_date,
         "description": f"فاتورة مورد {bill.doc_number}", "source_module": "purchases",
         "source_document_id": bill.id, "source_event_key": f"purchases.bill.{bill.id}.v1",
         "currency_id": bill.currency_id, "exchange_rate": fx},
        lines, actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    bill.journal_entry_id = entry.id
    bill.event_key = entry.source_event_key
    bill.status = "posted"
    db.session.commit()
    from . import audit_service as _audit_svc
    _audit_svc.record(tenant_id=bill.tenant_id, actor_id=actor_id, action="post",
                      entity_type="vendor_bills", entity_id=bill.id,
                      new={"doc_number": bill.doc_number})
    db.session.commit()
    return bill


def create_payment(*, tenant_id, entity_id, supplier_id, pay_date: date,
                   pay_method="bank_transfer", amount, currency_id="JOD", exchange_rate=1,
                   actor_id) -> VendorPayment:
    tenant_id, entity_id, supplier_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, supplier_id))
    try:
        fx = float(exchange_rate or 1)
    except (TypeError, ValueError):
        fx = 1
    if fx <= 0:
        raise ValidationError("exchange_rate must be > 0")
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="payment", year=pay_date.year)
    pay = VendorPayment(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                        supplier_id=supplier_id, pay_date=pay_date, pay_method=pay_method,
                        currency_id=currency_id, exchange_rate=fx, amount=amount, allocated_amount=0,
                        unallocated_amount=amount, status="confirmed",
                        created_by=actor_id, updated_by=actor_id)
    db.session.add(pay)
    db.session.commit()
    return pay


def post_payment(payment_id: uuid.UUID, *, cash_account_id, actor_id,
                 journal_code: str = "BANK") -> VendorPayment:
    """ترحيل الدفعة: مورد مدين / نقدية دائنة."""
    pay = db.session.get(VendorPayment, payment_id)
    if pay is None or pay.is_deleted:
        raise NotFoundError("Payment not found")
    if pay.status == "posted":
        return pay
    if pay.status != "confirmed":
        raise BadStateError(f"Cannot post from {pay.status}")
    from . import approval_service as _appr2
    _appr2.check_doc_rule(tenant_id=pay.tenant_id, entity_id=pay.entity_id,
                          doc_type="payment", total=float(pay.amount),
                          creator_id=pay.created_by, poster_id=actor_id)
    from ..models.journal import Journal as _Journal
    journal = db.session.query(_Journal).filter_by(
        tenant_id=pay.tenant_id, entity_id=pay.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    supplier_acc = _account(pay.entity_id, "2010")
    entry = posting_service.create_entry(
        {"tenant_id": pay.tenant_id, "entity_id": pay.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": pay.pay_date, "posting_date": pay.pay_date,
         "description": f"دفعة مورد {pay.doc_number}", "source_module": "purchases",
         "source_document_id": pay.id, "source_event_key": f"purchases.payment.{pay.id}.v1",
         "currency_id": pay.currency_id, "exchange_rate": float(pay.exchange_rate or 1)},
        [{"account_id": supplier_acc.id, "debit": float(pay.amount), "credit": 0,
          "partner_id": pay.supplier_id},
         {"account_id": uuid.UUID(str(cash_account_id)), "debit": 0, "credit": float(pay.amount),
          "partner_id": pay.supplier_id}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    pay.journal_entry_id = entry.id
    pay.event_key = entry.source_event_key
    pay.status = "posted"
    db.session.commit()
    return pay


def allocate(*, payment_id, allocations: list[dict], actor_id) -> VendorPayment:
    pay = db.session.get(VendorPayment, payment_id)
    if pay is None or pay.is_deleted:
        raise NotFoundError("Payment not found")
    if pay.status != "posted":
        raise BadStateError(f"Allocate requires posted payment (now {pay.status}) — post first")
    total = sum(Decimal(str(a["allocated_amount"])) for a in allocations)
    if total > Decimal(str(pay.unallocated_amount)):
        raise ValidationError(f"Over-allocation: {total}")
    for a in allocations:
        bill = db.session.get(VendorBill, uuid.UUID(str(a["bill_id"])))
        if bill is None or bill.is_deleted or bill.status not in ("posted", "partially_paid"):
            raise ValidationError(f"Bill not payable: {a['bill_id']}")
        if str(bill.supplier_id) != str(pay.supplier_id):
            raise ValidationError("Payment supplier differs from bill supplier")
        if str(bill.entity_id) != str(pay.entity_id) or str(bill.tenant_id) != str(pay.tenant_id):
            raise ValidationError("Entity/tenant mismatch between payment and bill")
        if Decimal(str(a["allocated_amount"])) > Decimal(str(bill.remaining_amount)):
            raise ValidationError(f"Exceeds bill remainder: {bill.doc_number}")
        db.session.add(VendorPaymentAllocation(
            tenant_id=pay.tenant_id, payment_id=pay.id, bill_id=bill.id,
            allocated_amount=a["allocated_amount"], allocated_by=actor_id,
            created_by=actor_id, updated_by=actor_id))
        bill.paid_amount = float(Decimal(str(bill.paid_amount)) + Decimal(str(a["allocated_amount"])))
        bill.remaining_amount = float(Decimal(str(bill.remaining_amount)) - Decimal(str(a["allocated_amount"])))
        bill.status = "paid" if bill.remaining_amount <= 0.001 else "partially_paid"
    pay.allocated_amount = float(Decimal(str(pay.allocated_amount)) + total)
    pay.unallocated_amount = float(Decimal(str(pay.unallocated_amount)) - total)
    db.session.commit()
    return pay
