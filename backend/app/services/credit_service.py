"""Credit notes + customer returns (AR reductions with stock receipt)."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.sales import (
    CreditNote, CreditNoteLine, CustomerReturn, CustomerReturnLine,
)
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, AccountingError

log = logging.getLogger(__name__)


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def create_credit_note(*, tenant_id, entity_id, customer_id, invoice_id=None,
                       note_date=None, reason, currency_id="JOD", lines, notes=None,
                       actor_id) -> CreditNote:
    tenant_id, entity_id, customer_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, customer_id))
    note_date = note_date or date.today()
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="credit_note", year=note_date.year)
    sub = sum(Decimal(str(l.get("qty", 1))) * Decimal(str(l["unit_price"])) for l in lines)
    note = CreditNote(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                      customer_id=customer_id,
                      invoice_id=uuid.UUID(str(invoice_id)) if invoice_id else None,
                      note_date=note_date, reason=reason, currency_id=currency_id,
                      subtotal=sub, grand_total=sub, status="draft", notes=notes,
                      created_by=actor_id, updated_by=actor_id)
    db.session.add(note)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        db.session.add(CreditNoteLine(
            tenant_id=tenant_id, note_id=note.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])) if l.get("product_id") else None,
            qty=l.get("qty", 1), unit_price=l["unit_price"],
            discount_pct=l.get("discount_pct", 0),
            tax_id=uuid.UUID(str(l["tax_id"])) if l.get("tax_id") else None,
            line_total=Decimal(str(l.get("qty", 1))) * Decimal(str(l["unit_price"])),
            account_id=uuid.UUID(str(l["account_id"])) if l.get("account_id") else None,
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return note


def post_credit_note(note_id: uuid.UUID, *, actor_id, journal_code: str = "SALE") -> CreditNote:
    note = db.session.get(CreditNote, note_id)
    if note is None or note.is_deleted:
        raise NotFoundError("Credit note not found")
    if note.status == "posted":
        return note
    if note.status != "draft":
        raise BadStateError(f"Cannot post from {note.status}")
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=note.tenant_id, entity_id=note.entity_id, code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    recv = _account(note.entity_id, "1210")
    rev_default = _account(note.entity_id, "4010")
    lines = []
    for l in note.lines:
        if l.is_deleted:
            continue
        lines.append({"account_id": l.account_id or rev_default.id,
                      "debit": float(l.line_total), "credit": 0,
                      "partner_id": note.customer_id})
    lines.append({"account_id": recv.id, "debit": 0, "credit": float(note.grand_total),
                  "partner_id": note.customer_id})
    entry = posting_service.create_entry(
        {"tenant_id": note.tenant_id, "entity_id": note.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": note.note_date, "posting_date": note.note_date,
         "description": f"credit {note.doc_number}", "source_module": "sales",
         "source_document_id": note.id, "source_event_key": f"sales.credit.{note.id}.v1",
         "currency_id": note.currency_id},
        lines, actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    note.journal_entry_id = entry.id
    note.event_key = entry.source_event_key
    note.status = "posted"
    db.session.commit()
    return note


def create_return(*, tenant_id, entity_id, customer_id, invoice_id=None,
                  return_date=None, reason, warehouse_id=None, currency_id="JOD",
                  lines, notes=None, actor_id) -> CustomerReturn:
    tenant_id, entity_id, customer_id = (uuid.UUID(str(x)) for x in (tenant_id, entity_id, customer_id))
    return_date = return_date or date.today()
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="return", year=return_date.year)
    total = sum(Decimal(str(l["returned_qty"])) * Decimal(str(l["unit_price"])) for l in lines)
    ret = CustomerReturn(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                         customer_id=customer_id,
                         invoice_id=uuid.UUID(str(invoice_id)) if invoice_id else None,
                         return_date=return_date, reason=reason,
                         warehouse_id=uuid.UUID(str(warehouse_id)) if warehouse_id else None,
                         currency_id=currency_id, total_amount=total, status="draft",
                         notes=notes, created_by=actor_id, updated_by=actor_id)
    db.session.add(ret)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        db.session.add(CustomerReturnLine(
            tenant_id=tenant_id, return_id=ret.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), returned_qty=l["returned_qty"],
            unit_price=l["unit_price"], discount_pct=l.get("discount_pct", 0),
            line_total=Decimal(str(l["returned_qty"])) * Decimal(str(l["unit_price"])),
            condition=l.get("condition", "good"),
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return ret


def post_return(return_id: uuid.UUID, *, actor_id, stock_account_code: str = "1310") -> CustomerReturn:
    ret = db.session.get(CustomerReturn, return_id)
    if ret is None or ret.is_deleted:
        raise NotFoundError("Return not found")
    if ret.status == "posted":
        return ret
    if ret.status != "draft":
        raise BadStateError(f"Cannot post from {ret.status}")
    from ..models.product import Product, StockMove, StockQuant, Location
    stock_acc = _account(ret.entity_id, stock_account_code)
    loc = None
    if ret.warehouse_id:
        loc = db.session.query(Location).filter_by(warehouse_id=ret.warehouse_id, is_deleted=False).first()
    cn_lines = []
    for l in ret.lines:
        if l.is_deleted:
            continue
        product = db.session.get(Product, l.product_id)
        move = StockMove(tenant_id=ret.tenant_id, entity_id=ret.entity_id,
                         product_id=product.id,
                         uom_id=product.base_uom_id, qty=float(l.returned_qty),
                         dest_location_id=loc.id if loc else None,
                         move_type="return", status="done", reference=ret.doc_number,
                         move_date=ret.return_date,
                         unit_cost=float(product.avg_cost or product.standard_cost or 0),
                         created_by=actor_id, updated_by=actor_id)
        db.session.add(move)
        db.session.flush()
        if loc:
            q = db.session.query(StockQuant).filter_by(product_id=product.id, location_id=loc.id).first()
            if q is None:
                q = StockQuant(tenant_id=ret.tenant_id, product_id=product.id, location_id=loc.id,
                               qty=0, reserved_qty=0, created_by=actor_id, updated_by=actor_id)
                db.session.add(q)
                db.session.flush()
            q.qty = float(q.qty) + float(l.returned_qty)
        cn_lines.append({"product_id": product.id, "qty": float(l.returned_qty),
                         "unit_price": float(l.unit_price), "account_id": stock_acc.id})
    note = create_credit_note(tenant_id=ret.tenant_id, entity_id=ret.entity_id,
                              customer_id=ret.customer_id, invoice_id=ret.invoice_id,
                              note_date=ret.return_date, reason=f"return {ret.doc_number}: {ret.reason}",
                              currency_id=ret.currency_id, lines=cn_lines, actor_id=actor_id)
    post_credit_note(note.id, actor_id=actor_id)
    # عكس تكلفة المبيعات: مخزون مدين / تكلفة دائنة بمتوسط التكلفة
    rev_total = 0.0
    for l in ret.lines:
        if l.is_deleted:
            continue
        product = db.session.get(Product, l.product_id)
        rev_total += round(float(l.returned_qty) * float(product.avg_cost or 0), 3)
    rev_total = round(rev_total, 3)
    if rev_total > 0:
        from ..models.journal import Journal
        journal = db.session.query(Journal).filter_by(
            tenant_id=ret.tenant_id, entity_id=ret.entity_id, code="SALE", is_deleted=False).first()
        if journal is None:
            journal = db.session.query(Journal).filter_by(
                tenant_id=ret.tenant_id, entity_id=ret.entity_id, code="GEN", is_deleted=False).first()
        if journal is None:
            raise NotFoundError("Journal SALE/GEN not configured")
        cogs_acc = _account(ret.entity_id, "5010")
        entry = posting_service.create_entry(
            {"tenant_id": ret.tenant_id, "entity_id": ret.entity_id, "journal_id": journal.id,
             "entry_type": "source", "document_date": ret.return_date, "posting_date": ret.return_date,
             "description": f"عكس تكلفة مرتجع {ret.doc_number}", "source_module": "sales",
             "source_document_id": ret.id, "source_event_key": f"sales.return.{ret.id}.cogs-rev.v1",
             "currency_id": ret.currency_id},
            [{"account_id": stock_acc.id, "debit": rev_total, "credit": 0},
             {"account_id": cogs_acc.id, "debit": 0, "credit": rev_total}],
            actor_id=actor_id)
        posting_service.post_entry(entry.id, actor_id)
    ret.status = "posted"
    db.session.commit()
    return ret
