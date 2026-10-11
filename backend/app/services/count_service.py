"""Stock count cycle: draft -> counting -> approved -> posted.

- snapshot: captures system_qty per product/location in the warehouse.
- submit: records counted quantities.
- approve: locks the count (all lines must be counted).
- apply: creates posted adjustment moves for every nonzero difference and
  updates quants (surplus uses line unit_cost for average-cost update).
No deletions: the cycle completes inside the existing inventory module.
"""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.product import Product, StockQuant, StockMove, Location, StockCount, StockCountLine
from . import sequence_service
from .errors import NotFoundError, BadStateError, ValidationError

log = logging.getLogger(__name__)


def _get_count(count_id) -> StockCount:
    c = db.session.get(StockCount, uuid.UUID(str(count_id)))
    if c is None or c.is_deleted:
        raise NotFoundError("Count not found")
    return c


def create_count(*, tenant_id, entity_id, warehouse_id, count_date=None,
                 notes=None, actor_id) -> StockCount:
    tenant_id = uuid.UUID(str(tenant_id))
    entity_id = uuid.UUID(str(entity_id))
    warehouse_id = uuid.UUID(str(warehouse_id))
    cdate = count_date or date.today()
    number = sequence_service.next_doc_number(
        tenant_id=tenant_id, entity_id=entity_id, doctype="count", year=cdate.year)
    c = StockCount(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                   warehouse_id=warehouse_id, count_date=cdate, status="draft",
                   notes=notes, created_by=actor_id, updated_by=actor_id)
    db.session.add(c)
    db.session.commit()
    return c


def snapshot(count_id, *, actor_id) -> StockCount:
    """لقطة الأرصدة النظامية لبنود المستودع (تُبنى مرة واحدة في draft)."""
    c = _get_count(count_id)
    if c.status != "draft":
        raise BadStateError(f"Cannot snapshot from {c.status}")
    if db.session.query(StockCountLine).filter_by(count_id=c.id, is_deleted=False).first():
        raise BadStateError("Snapshot already taken")
    locs = db.session.query(Location).filter_by(
        warehouse_id=c.warehouse_id, is_deleted=False).all()
    if not locs:
        raise ValidationError("Warehouse has no locations")
    loc_ids = {l.id for l in locs}
    quants = db.session.query(StockQuant).filter(
        StockQuant.location_id.in_(loc_ids),
        StockQuant.is_deleted.is_(False)).all()
    n = 0
    for q in quants:
        if abs(float(q.qty)) < 0.0000005 and abs(float(q.reserved_qty)) < 0.0000005:
            continue
        product = db.session.get(Product, q.product_id)
        n += 1
        db.session.add(StockCountLine(
            tenant_id=c.tenant_id, count_id=c.id, line_number=n,
            product_id=q.product_id, location_id=q.location_id,
            system_qty=float(q.qty), counted_qty=None,
            unit_cost=float(product.avg_cost or 0) if product else 0,
            created_by=actor_id, updated_by=actor_id))
    if not n:
        raise ValidationError("No stock to count in this warehouse")
    db.session.commit()
    return c


def start(count_id, *, actor_id) -> StockCount:
    c = _get_count(count_id)
    if c.status != "draft":
        raise BadStateError(f"Cannot start from {c.status}")
    if not db.session.query(StockCountLine).filter_by(count_id=c.id, is_deleted=False).first():
        raise BadStateError("Take a snapshot first")
    c.status = "counting"
    c.updated_by = actor_id
    db.session.commit()
    return c


def submit(count_id, *, items: list[dict], actor_id) -> StockCount:
    """تسجيل الكميات المعدودة: [{line_id, counted_qty}]."""
    c = _get_count(count_id)
    if c.status != "counting":
        raise BadStateError(f"Cannot submit from {c.status} — start the count first")
    by_id = {str(l.id): l for l in db.session.query(StockCountLine).filter_by(
        count_id=c.id, is_deleted=False).all()}
    if not items:
        raise ValidationError("No counted lines submitted")
    for it in items:
        line = by_id.get(str(it.get("line_id")))
        if line is None:
            raise ValidationError(f"Unknown count line: {it.get('line_id')}")
        try:
            qty = float(it["counted_qty"])
        except (TypeError, ValueError, KeyError):
            raise ValidationError(f"Invalid counted_qty for line {line.line_number}")
        if qty < 0:
            raise ValidationError(f"Negative counted_qty on line {line.line_number}")
        line.counted_qty = qty
        line.updated_by = actor_id
    db.session.commit()
    return c


def approve(count_id, *, actor_id) -> StockCount:
    c = _get_count(count_id)
    if c.status != "counting":
        raise BadStateError(f"Cannot approve from {c.status}")
    lines = db.session.query(StockCountLine).filter_by(count_id=c.id, is_deleted=False).all()
    pending = [l.line_number for l in lines if l.counted_qty is None]
    if pending:
        raise ValidationError(f"Lines not counted yet: {pending[:10]}")
    c.status = "approved"
    c.updated_by = actor_id
    db.session.commit()
    return c


def apply(count_id, *, actor_id) -> dict:
    """ترحيل الفروقات: حركة تسوية مرحّلة لكل فرق غير صفري + تحديث الأرصدة."""
    c = _get_count(count_id)
    if c.status != "approved":
        raise BadStateError(f"Cannot apply from {c.status} — approve first")
    lines = db.session.query(StockCountLine).filter_by(
        count_id=c.id, is_deleted=False).order_by(StockCountLine.line_number).all()
    created = 0
    for l in lines:
        diff = round(float(l.counted_qty or 0) - float(l.system_qty or 0), 6)
        if abs(diff) < 0.0000005:
            continue
        product = db.session.get(Product, l.product_id)
        move = StockMove(
            tenant_id=c.tenant_id, entity_id=c.entity_id,
            product_id=l.product_id, uom_id=product.base_uom_id,
            qty=abs(diff),
            source_location_id=l.location_id if diff < 0 else None,
            dest_location_id=l.location_id if diff > 0 else None,
            move_type="adjustment", status="done",
            reference=f"{c.doc_number}/L{l.line_number}",
            move_date=c.count_date, unit_cost=float(l.unit_cost or 0),
            created_by=actor_id, updated_by=actor_id)
        db.session.add(move)
        q = db.session.query(StockQuant).filter_by(
            product_id=l.product_id, location_id=l.location_id).first()
        if q is None:
            q = StockQuant(tenant_id=c.tenant_id, product_id=l.product_id,
                           location_id=l.location_id, qty=0, reserved_qty=0,
                           created_by=actor_id, updated_by=actor_id)
            db.session.add(q)
            db.session.flush()
        old_qty = float(q.qty)
        q.qty = old_qty + diff
        if float(q.qty) < -0.000001:
            raise ValidationError(f"Count would drive negative stock (line {l.line_number})")
        if diff > 0 and float(l.unit_cost or 0) > 0 and float(q.qty) > 0:
            q_total_before = old_qty
            product.avg_cost = round(
                (float(product.avg_cost or 0) * q_total_before
                 + float(l.unit_cost) * diff) / float(q.qty), 3)
        created += 1
    c.status = "posted"
    c.updated_by = actor_id
    db.session.commit()
    log.info("count %s applied: %s adjustment moves", c.doc_number, created)
    return {"count_id": str(c.id), "status": c.status, "adjustment_moves": created}


def diff_report(count_id) -> list[dict]:
    c = _get_count(count_id)
    lines = db.session.query(StockCountLine).filter_by(
        count_id=c.id, is_deleted=False).order_by(StockCountLine.line_number).all()
    out = []
    for l in lines:
        product = db.session.get(Product, l.product_id)
        diff = (None if l.counted_qty is None
                else round(float(l.counted_qty) - float(l.system_qty or 0), 6))
        out.append({"line_id": str(l.id), "line_number": l.line_number,
                    "product_id": str(l.product_id),
                    "product_code": product.code if product else "?",
                    "product_name": product.name_ar if product else "?",
                    "location_id": str(l.location_id) if l.location_id else None,
                    "system_qty": float(l.system_qty or 0),
                    "counted_qty": None if l.counted_qty is None else float(l.counted_qty),
                    "diff": diff})
    return out
