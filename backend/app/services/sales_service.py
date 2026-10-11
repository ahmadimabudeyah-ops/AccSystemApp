"""Sales service: invoices (totals+tax), auto-posting, payments, allocations, JoFotara queue."""
from __future__ import annotations
import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import text as _text
from ..extensions import db
from ..models.sales import (
    CustomerInvoice, CustomerInvoiceLine, CustomerInvoiceTax,
    CustomerPayment, PaymentAllocation,
)
from ..models.product import Product
from ..models.treasury import Tax
from . import posting_service, sequence_service
from .errors import (
    NotFoundError, BadStateError, ValidationError, AccountingError,
)

log = logging.getLogger(__name__)


def _account(model, entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def compute_totals(lines: list[dict]) -> dict:
    """Totals per line: qty*price*(1-disc) + tax by tax_id rate."""
    sub = Decimal("0")
    tax = Decimal("0")
    enriched = []
    for l in lines:
        qty = Decimal(str(l["qty"]))
        price = Decimal(str(l["unit_price"]))
        disc = Decimal(str(l.get("discount_pct", 0))) / 100
        net = qty * price * (1 - disc)
        rate = Decimal("0")
        tax_id = l.get("tax_id")
        if tax_id:
            t = db.session.get(Tax, uuid.UUID(str(tax_id)))
            if t is None or not t.is_active:
                raise ValidationError(f"Invalid tax: {tax_id}")
            rate = Decimal(str(t.rate))
        t_amount = (net * rate / 100).quantize(Decimal("0.001"))
        sub += net
        tax += t_amount
        enriched.append({**l, "net": net, "tax_amount": t_amount, "tax_rate": rate})
    return {"subtotal": sub, "tax_total": tax, "grand_total": sub + tax, "lines": enriched}


def create_invoice(*, tenant_id, entity_id, customer_id, invoice_date: date,
                   payment_term_days: int = 0, currency_id="JOD", exchange_rate=1,
                   lines: list[dict],
                   reference=None, notes=None, actor_id) -> CustomerInvoice:
    tenant_id, entity_id, customer_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, customer_id))
    if not lines:
        raise ValidationError("Invoice needs at least one line")
    try:
        fx = float(exchange_rate or 1)
    except (TypeError, ValueError):
        fx = 1
    if fx <= 0:
        raise ValidationError("exchange_rate must be > 0")
    totals = compute_totals([{**l, "product_id": uuid.UUID(str(l["product_id"])),
                              "tax_id": uuid.UUID(str(l["tax_id"])) if l.get("tax_id") else None}
                             for l in lines])
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id, doctype="invoice",
                                              year=invoice_date.year)
    inv = CustomerInvoice(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                          customer_id=customer_id, invoice_date=invoice_date,
                          due_on=invoice_date + timedelta(days=payment_term_days),
                          currency_id=currency_id, exchange_rate=fx, subtotal=totals["subtotal"],
                          tax_total=totals["tax_total"], grand_total=totals["grand_total"],
                          paid_amount=0, remaining_amount=totals["grand_total"],
                          status="draft", reference=reference, notes=notes,
                          created_by=actor_id, updated_by=actor_id)
    db.session.add(inv)
    db.session.flush()
    for i, l in enumerate(totals["lines"], 1):
        product = db.session.get(Product, l["product_id"])
        if product is None:
            raise ValidationError(f"Unknown product: {l['product_id']}")
        db.session.add(CustomerInvoiceLine(
            tenant_id=tenant_id, invoice_id=inv.id, line_number=i, product_id=product.id,
            description=l.get("description", product.name_ar), qty=l["qty"],
            unit_price=l["unit_price"], discount_pct=l.get("discount_pct", 0),
            tax_id=l.get("tax_id"), line_total=l["net"] + l["tax_amount"],
            account_id=uuid.UUID(str(l["account_id"])) if l.get("account_id") else None,
            created_by=actor_id, updated_by=actor_id))
        if l.get("tax_id"):
            db.session.add(CustomerInvoiceTax(
                tenant_id=tenant_id, invoice_id=inv.id, line_id=None,
                tax_id=l["tax_id"], tax_rate=l["tax_rate"], tax_amount=l["tax_amount"],
                created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    log.info("invoice created %s total=%s", number, totals["grand_total"])
    return inv


def post_invoice(invoice_id: uuid.UUID, *, actor_id, journal_code: str = "SALE") -> CustomerInvoice:
    """ترحيل الفاتورة: عميل مدين / إيراد + ضريبة دائنة + صف JoFotara."""
    inv = db.session.get(CustomerInvoice, invoice_id)
    if inv is None or inv.is_deleted:
        raise NotFoundError("Invoice not found")
    if inv.status == "posted":
        return inv
    if inv.status != "draft":
        raise BadStateError(f"Cannot post from {inv.status}")
    from . import approval_service as _appr
    _appr.check_doc_rule(tenant_id=inv.tenant_id, entity_id=inv.entity_id,
                         doc_type="invoice", total=float(inv.grand_total),
                         creator_id=inv.created_by, poster_id=actor_id)
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=inv.tenant_id, entity_id=inv.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    recv = _account(None, inv.entity_id, "1210")
    vat = _account(None, inv.entity_id, "2140")
    rev_default = _account(None, inv.entity_id, "4010")
    lines = [{"account_id": recv.id, "debit": float(inv.grand_total), "credit": 0,
              "partner_id": inv.customer_id}]
    rev_by_acc: dict[str, float] = {}
    for l in inv.lines:
        if l.is_deleted:
            continue
        key = str(l.account_id or rev_default.id)
        rev_by_acc[key] = rev_by_acc.get(key, 0.0) + float(l.qty) * float(l.unit_price) * (
            1 - float(l.discount_pct or 0) / 100)
    for acc_id, amount in rev_by_acc.items():
        lines.append({"account_id": uuid.UUID(acc_id), "debit": 0, "credit": round(amount, 3),
                      "partner_id": inv.customer_id})
    if float(inv.tax_total) > 0:
        lines.append({"account_id": vat.id, "debit": 0, "credit": float(inv.tax_total),
                      "partner_id": inv.customer_id})
    entry = posting_service.create_entry(
        {"tenant_id": inv.tenant_id, "entity_id": inv.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": inv.invoice_date, "posting_date": inv.invoice_date,
         "description": f"فاتورة {inv.doc_number}", "source_module": "sales",
         "source_document_id": inv.id, "source_event_key": f"sales.invoice.{inv.id}.v1",
         "currency_id": inv.currency_id, "exchange_rate": float(inv.exchange_rate or 1)},
        lines, actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    inv.journal_entry_id = entry.id
    inv.event_key = entry.source_event_key
    inv.status = "posted"
    inv.posted_at = entry.posted_at
    db.session.execute(_text(
        "INSERT INTO einvoicing_queue(tenant_id, invoice_id, einv_status, priority, created_by, updated_by)"
        " VALUES (:t, :i, 'queued', 100, :u, :u) ON CONFLICT DO NOTHING"),
        {"t": inv.tenant_id, "i": inv.id, "u": actor_id})
    db.session.commit()
    log.info("invoice posted %s entry=%s", inv.doc_number, entry.id)
    from . import audit_service as _audit_svc
    _audit_svc.record(tenant_id=inv.tenant_id, actor_id=actor_id, action="post",
                      entity_type="customer_invoices", entity_id=inv.id,
                      new={"doc_number": inv.doc_number, "total": float(inv.grand_total)})
    db.session.commit()
    return inv


def create_payment(*, tenant_id, entity_id, customer_id, pay_date: date,
                   pay_method="cash", amount, currency_id="JOD", exchange_rate=1,
                   reference=None, actor_id) -> CustomerPayment:
    from . import sequence_service as _seq
    tenant_id, entity_id, customer_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, customer_id))
    try:
        fx = float(exchange_rate or 1)
    except (TypeError, ValueError):
        fx = 1
    if fx <= 0:
        raise ValidationError("exchange_rate must be > 0")
    number = _seq.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                  doctype="payment", year=pay_date.year)
    pay = CustomerPayment(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                          customer_id=customer_id, pay_date=pay_date, pay_method=pay_method,
                          currency_id=currency_id, exchange_rate=fx, amount=amount, allocated_amount=0,
                          unallocated_amount=amount, status="confirmed",
                          reference=reference, created_by=actor_id, updated_by=actor_id)
    db.session.add(pay)
    db.session.commit()
    return pay


def allocate(*, payment_id, allocations: list[dict], actor_id) -> CustomerPayment:
    """تخصيص دفعة على فواتير + لفّ المتبقي والحالات تلقائيًا."""
    pay = db.session.get(CustomerPayment, payment_id)
    if pay is None or pay.is_deleted:
        raise NotFoundError("Payment not found")
    if pay.status != "posted":
        raise BadStateError(f"Allocate requires posted payment (now {pay.status}) — post first")
    total = sum(Decimal(str(a["allocated_amount"])) for a in allocations)
    free = Decimal(str(pay.unallocated_amount))
    if total > free:
        raise ValidationError(f"Over-allocation: {total} > free {free}")
    for a in allocations:
        inv = db.session.get(CustomerInvoice, uuid.UUID(str(a["invoice_id"])))
        if inv is None or inv.is_deleted or inv.status not in ("posted", "partially_paid"):
            raise ValidationError(f"Invoice not payable: {a['invoice_id']}")
        if str(inv.customer_id) != str(pay.customer_id):
            raise ValidationError("Payment customer differs from invoice customer")
        if str(inv.entity_id) != str(pay.entity_id) or str(inv.tenant_id) != str(pay.tenant_id):
            raise ValidationError("Entity/tenant mismatch between payment and invoice")
        if str(inv.currency_id) != str(pay.currency_id):
            raise ValidationError("Currency mismatch between payment and invoice")
        if Decimal(str(a["allocated_amount"])) > Decimal(str(inv.remaining_amount)):
            raise ValidationError(f"Exceeds invoice remainder: {inv.doc_number}")
        db.session.add(PaymentAllocation(
            tenant_id=pay.tenant_id, payment_id=pay.id, invoice_id=inv.id,
            allocated_amount=a["allocated_amount"], currency_id=pay.currency_id,
            allocated_by=actor_id, created_by=actor_id, updated_by=actor_id))
        inv.paid_amount = float(Decimal(str(inv.paid_amount)) + Decimal(str(a["allocated_amount"])))
        inv.remaining_amount = float(Decimal(str(inv.remaining_amount)) - Decimal(str(a["allocated_amount"])))
        inv.status = "paid" if inv.remaining_amount <= 0.001 else "partially_paid"
    pay.allocated_amount = float(Decimal(str(pay.allocated_amount)) + total)
    pay.unallocated_amount = float(Decimal(str(pay.unallocated_amount)) - total)
    db.session.commit()
    return pay


def post_payment(payment_id: uuid.UUID, *, cash_account_id, actor_id,
                 journal_code: str = "CASH") -> CustomerPayment:
    """ترحيل الدفعة: نقدية مدينة / عميل دائنة (تخفيض الذمة)."""
    pay = db.session.get(CustomerPayment, payment_id)
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
    recv = _account(None, pay.entity_id, "1210")
    entry = posting_service.create_entry(
        {"tenant_id": pay.tenant_id, "entity_id": pay.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": pay.pay_date, "posting_date": pay.pay_date,
         "description": f"تحصيل {pay.doc_number}", "source_module": "sales",
         "source_document_id": pay.id, "source_event_key": f"sales.payment.{pay.id}.v1",
         "currency_id": pay.currency_id, "exchange_rate": float(pay.exchange_rate or 1)},
        [{"account_id": uuid.UUID(str(cash_account_id)), "debit": float(pay.amount), "credit": 0,
          "partner_id": pay.customer_id},
         {"account_id": recv.id, "debit": 0, "credit": float(pay.amount),
          "partner_id": pay.customer_id}],
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    pay.journal_entry_id = entry.id
    pay.event_key = entry.source_event_key
    pay.status = "posted"
    db.session.commit()
    return pay
