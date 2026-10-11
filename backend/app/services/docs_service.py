"""Document flows: quote->order->delivery->invoice, request->order->receipt->bill."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.docs import (
    Quotation, QuotationLine, SalesOrder, SalesOrderLine,
    Delivery, DeliveryLine, PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine,
)
from ..models.product import Product, StockMove, StockQuant, Location
from . import sequence_service
from .errors import NotFoundError, BadStateError, ValidationError, AccountingError

log = logging.getLogger(__name__)


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


def _totals(lines):
    sub = sum(Decimal(str(l["qty"])) * Decimal(str(l["unit_price"]))
              * (1 - Decimal(str(l.get("discount_pct", 0))) / 100) for l in lines)
    return sub


# ------------------------------------------------------------- sales docs

def create_quotation(*, tenant_id, entity_id, customer_id, lines,
                     valid_days: int = 15, actor_id) -> Quotation:
    from datetime import timedelta
    tenant_id = uuid.UUID(str(tenant_id))
    number = sequence_service.next_doc_number(tenant_id=tenant_id,
                                              entity_id=uuid.UUID(str(entity_id)),
                                              doctype="quotation", year=date.today().year)
    sub = _totals([{**l, "qty": l.get("qty", l.get("ordered_qty", 1))} for l in lines])
    q = Quotation(tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
                  doc_number=number, customer_id=uuid.UUID(str(customer_id)),
                  quote_date=date.today(), valid_until=date.today() + timedelta(days=valid_days),
                  subtotal=sub, grand_total=sub, status="draft",
                  created_by=actor_id, updated_by=actor_id)
    db.session.add(q)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        db.session.add(QuotationLine(
            tenant_id=tenant_id, quotation_id=q.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), qty=l.get("qty", l.get("ordered_qty", 1)),
            unit_price=l["unit_price"], discount_pct=l.get("discount_pct", 0),
            line_total=Decimal(str(l.get("qty", 1))) * Decimal(str(l["unit_price"])),
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return q


def convert_quotation(quotation_id: uuid.UUID, *, actor_id) -> SalesOrder:
    q = db.session.get(Quotation, quotation_id)
    if q is None or q.is_deleted:
        raise NotFoundError("Quotation not found")
    if q.status not in ("draft", "approved", "sent"):
        raise BadStateError(f"Cannot convert from {q.status}")
    number = sequence_service.next_doc_number(tenant_id=q.tenant_id, entity_id=q.entity_id,
                                              doctype="sales_order", year=date.today().year)
    o = SalesOrder(tenant_id=q.tenant_id, entity_id=q.entity_id, doc_number=number,
                   customer_id=q.customer_id, order_date=date.today(),
                   subtotal=q.subtotal, grand_total=q.grand_total, status="confirmed",
                   quotation_id=q.id, created_by=actor_id, updated_by=actor_id)
    db.session.add(o)
    db.session.flush()
    for l in q.lines:
        if l.is_deleted:
            continue
        db.session.add(SalesOrderLine(
            tenant_id=q.tenant_id, order_id=o.id, line_number=l.line_number,
            product_id=l.product_id, ordered_qty=float(l.qty), unit_price=float(l.unit_price),
            discount_pct=float(l.discount_pct or 0), line_total=float(l.line_total),
            created_by=actor_id, updated_by=actor_id))
    q.status = "converted"
    db.session.commit()
    return o


def create_delivery(*, order_id, warehouse_id, lines: list[dict] | None = None,
                    actor_id) -> Delivery:
    o = db.session.get(SalesOrder, uuid.UUID(str(order_id)))
    if o is None or o.is_deleted:
        raise NotFoundError("Order not found")
    if o.status not in ("confirmed", "in_progress", "partially_delivered"):
        raise BadStateError(f"Cannot deliver from {o.status}")
    if not lines:
        lines = [{"product_id": l.product_id,
                  "requested_qty": float(l.ordered_qty) - float(l.delivered_qty)}
                 for l in o.lines if not l.is_deleted
                 and float(l.ordered_qty) - float(l.delivered_qty) > 0.001]
        if not lines:
            raise ValidationError("Order fully delivered")
    number = sequence_service.next_doc_number(tenant_id=o.tenant_id, entity_id=o.entity_id,
                                              doctype="delivery", year=date.today().year)
    d = Delivery(tenant_id=o.tenant_id, entity_id=o.entity_id, doc_number=number,
                 order_id=o.id, customer_id=o.customer_id, delivery_date=date.today(),
                 warehouse_id=uuid.UUID(str(warehouse_id)), status="draft",
                 created_by=actor_id, updated_by=actor_id)
    db.session.add(d)
    db.session.flush()
    from ..models.product import Location
    default_loc = db.session.query(Location).filter_by(
        warehouse_id=uuid.UUID(str(warehouse_id)), is_deleted=False).first()
    for i, l in enumerate(lines, 1):
        db.session.add(DeliveryLine(
            tenant_id=o.tenant_id, delivery_id=d.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])) if isinstance(l.get("product_id"), str) else l["product_id"],
            requested_qty=l["requested_qty"], delivered_qty=0,
            source_location_id=uuid.UUID(str(l["source_location_id"])) if l.get("source_location_id")
            else (default_loc.id if default_loc else None),
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return d


def confirm_delivery(delivery_id: uuid.UUID, *, actor_id) -> Delivery:
    """تأكيد التسليم: صرف مخزني حقيقي + تحديث كميات الأمر."""
    d = db.session.get(Delivery, delivery_id)
    if d is None or d.is_deleted:
        raise NotFoundError("Delivery not found")
    if d.status != "draft":
        raise BadStateError(f"Cannot confirm from {d.status}")
    for l in d.lines:
        if l.is_deleted:
            continue
        if l.source_location_id is None:
            raise ValidationError("Delivery line needs a source location")
        product = db.session.get(Product, l.product_id)
        q = db.session.query(StockQuant).filter_by(
            product_id=l.product_id, location_id=l.source_location_id).first()
        avail = float(q.qty) - float(q.reserved_qty) if q else 0.0
        if avail < float(l.requested_qty) - 0.001:
            raise ValidationError(f"Insufficient stock for {product.code if product else '?'}")
        move = StockMove(tenant_id=d.tenant_id, entity_id=d.entity_id,
                         product_id=l.product_id, uom_id=product.base_uom_id,
                         qty=float(l.requested_qty), source_location_id=l.source_location_id,
                         dest_location_id=None, move_type="delivery", status="done",
                         reference=d.doc_number, move_date=d.delivery_date,
                         unit_cost=float(product.avg_cost or 0),
                         created_by=actor_id, updated_by=actor_id)
        db.session.add(move)
        q.qty = float(q.qty) - float(l.requested_qty)
        l.delivered_qty = float(l.requested_qty)
        if d.order_id:
            sol = (db.session.query(SalesOrderLine)
                   .filter_by(order_id=d.order_id, product_id=l.product_id, is_deleted=False).first())
            if sol:
                sol.delivered_qty = float(sol.delivered_qty) + float(l.requested_qty)
    d.status = "delivered"
    if d.order_id:
        o = db.session.get(SalesOrder, d.order_id)
        lines = [x for x in o.lines if not x.is_deleted]
        o.status = ("fully_delivered" if all(float(x.delivered_qty) >= float(x.ordered_qty) - 0.001 for x in lines)
                    else "partially_delivered")
    # قيد تكلفة المبيعات الدائم: مصروف مدين / مخزون دائن بمتوسط التكلفة
    cogs_lines = []
    for l in d.lines:
        if l.is_deleted:
            continue
        product = db.session.get(Product, l.product_id)
        cost = round(float(l.requested_qty) * float(product.avg_cost or 0), 3)
        if cost <= 0:
            continue
        cogs_lines.append({"product_id": product.id, "qty": float(l.requested_qty), "cost": cost})
    if cogs_lines:
        from . import posting_service
        from ..models.journal import Journal
        journal = db.session.query(Journal).filter_by(
            tenant_id=d.tenant_id, entity_id=d.entity_id, code="SALE", is_deleted=False).first()
        if journal is None:
            journal = db.session.query(Journal).filter_by(
                tenant_id=d.tenant_id, entity_id=d.entity_id, code="GEN", is_deleted=False).first()
        if journal is None:
            raise NotFoundError("Journal SALE/GEN not configured")
        cogs_acc = _account(d.entity_id, "5010")
        stock_acc = _account(d.entity_id, "1310")
        total_cogs = round(sum(x["cost"] for x in cogs_lines), 3)
        entry = posting_service.create_entry(
            {"tenant_id": d.tenant_id, "entity_id": d.entity_id, "journal_id": journal.id,
             "entry_type": "source", "document_date": d.delivery_date, "posting_date": d.delivery_date,
             "description": f"تكلفة تسليم {d.doc_number}", "source_module": "sales",
             "source_document_id": d.id, "source_event_key": f"sales.delivery.{d.id}.cogs.v1",
             "currency_id": "JOD", "exchange_rate": 1},
            [{"account_id": cogs_acc.id, "debit": total_cogs, "credit": 0},
             {"account_id": stock_acc.id, "debit": 0, "credit": total_cogs}],
            actor_id=actor_id)
        posting_service.post_entry(entry.id, actor_id)
    db.session.commit()
    return d


# ------------------------------------------------------------- purchase docs

def create_request(*, tenant_id, entity_id, reason, lines, actor_id) -> PurchaseRequest:
    tenant_id = uuid.UUID(str(tenant_id))
    number = sequence_service.next_doc_number(tenant_id=tenant_id,
                                              entity_id=uuid.UUID(str(entity_id)),
                                              doctype="purchase_request", year=date.today().year)
    r = PurchaseRequest(tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
                        doc_number=number, request_date=date.today(), reason=reason,
                        status="draft", created_by=actor_id, updated_by=actor_id)
    db.session.add(r)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        db.session.add(PurchaseRequestLine(
            tenant_id=tenant_id, request_id=r.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), qty=l["qty"],
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return r


def approve_request(request_id: uuid.UUID, *, actor_id) -> PurchaseRequest:
    r = db.session.get(PurchaseRequest, request_id)
    if r is None or r.is_deleted:
        raise NotFoundError("Request not found")
    if r.status != "draft":
        raise BadStateError(f"Cannot approve from {r.status}")
    r.status = "approved"
    db.session.commit()
    return r


def create_order(*, tenant_id, entity_id, supplier_id, request_id=None,
                 lines, actor_id) -> PurchaseOrder:
    tenant_id = uuid.UUID(str(tenant_id))
    number = sequence_service.next_doc_number(tenant_id=tenant_id,
                                              entity_id=uuid.UUID(str(entity_id)),
                                              doctype="purchase_order", year=date.today().year)
    sub = sum(Decimal(str(l["ordered_qty"])) * Decimal(str(l["unit_price"])) for l in lines)
    o = PurchaseOrder(tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
                      doc_number=number, supplier_id=uuid.UUID(str(supplier_id)),
                      request_id=uuid.UUID(str(request_id)) if request_id else None,
                      order_date=date.today(), subtotal=sub, grand_total=sub,
                      status="confirmed", created_by=actor_id, updated_by=actor_id)
    db.session.add(o)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        total = Decimal(str(l["ordered_qty"])) * Decimal(str(l["unit_price"]))
        db.session.add(PurchaseOrderLine(
            tenant_id=tenant_id, order_id=o.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), ordered_qty=l["ordered_qty"],
            unit_price=l["unit_price"], line_total=total,
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return o


def create_receipt(*, order_id=None, tenant_id=None, entity_id=None, supplier_id=None,
                   warehouse_id, lines: list[dict] | None = None, actor_id) -> GoodsReceipt:
    if order_id:
        o = db.session.get(PurchaseOrder, uuid.UUID(str(order_id)))
        if o is None or o.is_deleted:
            raise NotFoundError("Order not found")
        tenant_id, entity_id, supplier_id = o.tenant_id, o.entity_id, o.supplier_id
        if not lines:
            lines = [{"product_id": l.product_id,
                      "received_qty": float(l.ordered_qty) - float(l.received_qty),
                      "unit_cost": float(l.unit_price)}
                     for l in o.lines if not l.is_deleted
                     and float(l.ordered_qty) - float(l.received_qty) > 0.001]
            if not lines:
                raise ValidationError("Order fully received")
    number = sequence_service.next_doc_number(tenant_id=uuid.UUID(str(tenant_id)),
                                              entity_id=uuid.UUID(str(entity_id)),
                                              doctype="receipt", year=date.today().year)
    g = GoodsReceipt(tenant_id=uuid.UUID(str(tenant_id)), entity_id=uuid.UUID(str(entity_id)),
                     doc_number=number,
                     order_id=uuid.UUID(str(order_id)) if order_id else None,
                     supplier_id=uuid.UUID(str(supplier_id)),
                     warehouse_id=uuid.UUID(str(warehouse_id)),
                     receipt_date=date.today(), status="draft",
                     created_by=actor_id, updated_by=actor_id)
    db.session.add(g)
    db.session.flush()
    from ..models.product import Location as _Loc2
    default_loc = None
    for i, l in enumerate(lines, 1):
        loc_id = l.get("location_id")
        if loc_id is None:
            if default_loc is None:
                default_loc = db.session.query(_Loc2).filter_by(
                    warehouse_id=g.warehouse_id, is_deleted=False).first()
            loc_id = default_loc.id if default_loc else None
        db.session.add(GoodsReceiptLine(
            tenant_id=g.tenant_id, receipt_id=g.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), received_qty=l["received_qty"],
            unit_cost=l.get("unit_cost", 0),
            location_id=uuid.UUID(str(loc_id)) if loc_id else None,
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return g


def confirm_receipt(receipt_id: uuid.UUID, *, actor_id) -> GoodsReceipt:
    """تأكيد الاستلام: إدخال مخزني + تحديث كميات الأمر + متوسط التكلفة."""
    g = db.session.get(GoodsReceipt, receipt_id)
    if g is None or g.is_deleted:
        raise NotFoundError("Receipt not found")
    if g.status != "draft":
        raise BadStateError(f"Cannot confirm from {g.status}")
    for l in g.lines:
        if l.is_deleted:
            continue
        if l.location_id is None:
            raise ValidationError("Receipt line needs a location")
        product = db.session.get(Product, l.product_id)
        move = StockMove(tenant_id=g.tenant_id, entity_id=g.entity_id,
                         product_id=l.product_id, uom_id=product.base_uom_id,
                         qty=float(l.received_qty), dest_location_id=l.location_id,
                         move_type="receipt", status="done", reference=g.doc_number,
                         move_date=g.receipt_date, unit_cost=float(l.unit_cost or 0),
                         created_by=actor_id, updated_by=actor_id)
        db.session.add(move)
        db.session.flush()
        q = db.session.query(StockQuant).filter_by(product_id=l.product_id, location_id=l.location_id).first()
        if q is None:
            q = StockQuant(tenant_id=g.tenant_id, product_id=l.product_id, location_id=l.location_id,
                           qty=0, reserved_qty=0, created_by=actor_id, updated_by=actor_id)
            db.session.add(q)
            db.session.flush()
        old_qty = float(q.qty)
        q.qty = old_qty + float(l.received_qty)
        if float(l.unit_cost or 0) > 0 and q.qty > 0:
            product.avg_cost = round((float(product.avg_cost) * old_qty
                                      + float(l.unit_cost) * float(l.received_qty)) / float(q.qty), 3)
        if g.order_id:
            pol = (db.session.query(PurchaseOrderLine)
                   .filter_by(order_id=g.order_id, product_id=l.product_id, is_deleted=False).first())
            if pol:
                pol.received_qty = float(pol.received_qty) + float(l.received_qty)
    g.status = "confirmed"
    if g.order_id:
        o = db.session.get(PurchaseOrder, g.order_id)
        olines = [x for x in o.lines if not x.is_deleted]
        o.status = ("fully_received" if all(float(x.received_qty) >= float(x.ordered_qty) - 0.001 for x in olines)
                    else "partially_received")
    db.session.commit()
    return g
