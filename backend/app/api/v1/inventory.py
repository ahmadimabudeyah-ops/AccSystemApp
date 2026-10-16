"""Inventory API: moves, quants, adjustments (with auto-posting on approve)."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.product import StockMove, StockQuant, Location, Product
from ...services import posting_service
from ...services.errors import AccountingError

bp = Blueprint("inventory", __name__)


def _deny(perm: str = "inventory.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


def _validate_locations(move_type, src, dst):
    """قواعد المواقع لكل نوع حركة — تمنع حركات بلا أثر."""
    if move_type == "receipt":
        if not dst or src:
            return "RECEIPT_NEEDS_DEST_ONLY"
    elif move_type == "delivery":
        if not src or dst:
            return "DELIVERY_NEEDS_SOURCE_ONLY"
    elif move_type == "internal":
        if not src or not dst or str(src) == str(dst):
            return "INTERNAL_NEEDS_BOTH_DIFFERENT"
    elif move_type == "adjustment":
        if bool(src) == bool(dst):
            return "ADJUSTMENT_NEEDS_EXACTLY_ONE"
    else:
        return "UNKNOWN_MOVE_TYPE"
    return None


@bp.get("/moves")
@jwt_required()
def list_moves():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(StockMove).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("product_id"):
        q = q.filter_by(product_id=uuid.UUID(str(request.args["product_id"])))
    if request.args.get("move_type"):
        q = q.filter_by(move_type=request.args["move_type"])
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    rows = q.order_by(StockMove.move_date.desc()).limit(50).offset((page - 1) * 50).all()
    out = []
    for m in rows:
        prod = db.session.get(Product, m.product_id)
        out.append({"id": str(m.id), "doc_number": m.reference or str(m.id)[:8],
                    "product_name": prod.name_ar if prod else "?",
                    "qty": float(m.qty), "move_type": m.move_type,
                    "status": m.status, "move_date": m.move_date.isoformat()})
    return jsonify({"data": out, "page": page})


@bp.post("/moves")
@jwt_required()
def create_move():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    try:
        qty = float(data.get("qty", 0))
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return jsonify({"error": {"code": "INVALID_QTY", "message": "qty must be > 0"}}), 400
    move_type = data.get("move_type", "internal")
    src = data.get("source_location_id") or None
    dst = data.get("dest_location_id") or None
    err = _validate_locations(move_type, src, dst)
    if err:
        return jsonify({"error": {"code": err}}), 400
    m = StockMove(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                  product_id=uuid.UUID(str(data["product_id"])),
                  uom_id=uuid.UUID(str(data["uom_id"])), qty=data["qty"],
                  source_location_id=uuid.UUID(str(data["source_location_id"])) if data.get("source_location_id") else None,
                  dest_location_id=uuid.UUID(str(data["dest_location_id"])) if data.get("dest_location_id") else None,
                  move_type=data.get("move_type", "internal"), status="draft",
                  reference=data.get("reference"), move_date=date.fromisoformat(data.get("move_date", str(date.today()))),
                  unit_cost=data.get("unit_cost", 0), created_by=me, updated_by=me)
    db.session.add(m)
    db.session.commit()
    return jsonify({"data": {"id": str(m.id), "status": "draft"}}), 201


@bp.post("/moves/<uuid:move_id>/done")
@jwt_required()
def done_move(move_id):
    """ترحيل الحركة: تحديث الأرصدة (ومنع السالب)."""
    denied = _deny()
    if denied:
        return denied
    m = db.session.get(StockMove, move_id)
    if m is None or m.is_deleted or str(m.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if m.status == "done":
        return jsonify({"data": {"id": str(m.id), "status": "done"}})
    if m.status != "draft":
        return jsonify({"error": {"code": "BAD_STATE"}}), 409
    if float(m.qty or 0) <= 0:
        return jsonify({"error": {"code": "INVALID_QTY"}}), 400
    err = _validate_locations(m.move_type, m.source_location_id, m.dest_location_id)
    if err:
        return jsonify({"error": {"code": err}}), 400

    def bump(location_id, delta):
        if location_id is None:
            return
        q = db.session.query(StockQuant).filter_by(product_id=m.product_id, location_id=location_id).first()
        if q is None:
            q = StockQuant(tenant_id=m.tenant_id, product_id=m.product_id, location_id=location_id,
                           qty=0, reserved_qty=0, created_by=m.created_by, updated_by=m.created_by)
            db.session.add(q)
            db.session.flush()
        if float(q.qty) + delta < -0.000001:
            return "INSUFFICIENT_STOCK"
        q.qty = float(q.qty) + delta

    err2 = bump(m.source_location_id, -float(m.qty))
    if err2:
        db.session.rollback()
        return jsonify({"error": {"code": err2,
                                  "message": "Insufficient stock"}}), 422
    bump(m.dest_location_id, float(m.qty))
    # تحديث متوسط التكلفة عند الاستلام بسعر
    if m.move_type == "receipt" and float(m.unit_cost or 0) > 0:
        p = db.session.get(Product, m.product_id)
        total_q = db.session.query(StockQuant).filter_by(product_id=m.product_id).all()
        on_hand = sum(float(x.qty) for x in total_q)
        if on_hand > 0:
            p.avg_cost = round((float(p.avg_cost) * (on_hand - float(m.qty)) + float(m.unit_cost) * float(m.qty)) / on_hand, 3)
    m.status = "done"
    m.updated_by = uuid.UUID(str(get_jwt().get("sub")))
    # قيد GL للحركات اليدوية: تسليم → كلفة مبيعات؛ تسوية → 5590
    _post_move_gl(m, actor_id=m.updated_by)
    db.session.commit()
    return jsonify({"data": {"id": str(m.id), "status": "done"}})


def _post_move_gl(m, *, actor_id):
    """ترحيل قيد محاسبي للحركة اليدوية المكتملة.

    - delivery: مصروف كلفة مدين / مخزون دائن (بمتوسط التكلفة)
    - adjustment (in): مخزون مدين / تسوية مخزون دائن
    - adjustment (out): تسوية مخزون مدين / مخزون دائن
    - receipt: لا قيد تلقائي (يجب أن يمر عبر فاتورة شراء أو قيد يدوي بحساب مقابل)
    """
    from ...models.journal import Journal
    from ...models.account import Account
    from ...services import posting_service as _ps
    from ...models.product import Product as _Prod
    if m.move_type == "internal":
        return  # تحويل داخلي بلا أثر مالي
    product = db.session.get(_Prod, m.product_id)
    if product is None or product.product_type != "stockable":
        return
    cost = round(float(m.qty) * float(product.avg_cost or 0), 3)
    if cost <= 0 and m.move_type != "adjustment":
        return
    journal = db.session.query(Journal).filter_by(
        tenant_id=m.tenant_id, entity_id=m.entity_id, code="GEN", is_deleted=False).first()
    if journal is None:
        return
    stock_acc = db.session.query(Account).filter_by(
        entity_id=m.entity_id, code="1310", is_deleted=False).first()
    if stock_acc is None:
        return
    if m.move_type == "delivery":
        cogs_acc = db.session.query(Account).filter_by(
            entity_id=m.entity_id, code="5010", is_deleted=False).first()
        if cogs_acc is None or cost <= 0:
            return
        lines = [{"account_id": cogs_acc.id, "debit": cost, "credit": 0},
                 {"account_id": stock_acc.id, "debit": 0, "credit": cost}]
        desc = f"كلفة تسليم مخزني {m.reference or m.id}"
    elif m.move_type == "adjustment":
        adj_acc = db.session.query(Account).filter_by(
            entity_id=m.entity_id, code="5590", is_deleted=False).first()
        if adj_acc is None:
            return
        # تحديد الاتجاه: إن وُجد dest → زيادة مخزون (مدين مخزون)؛ إن وُجد source → نقصان
        if m.dest_location_id and not m.source_location_id:
            lines = [{"account_id": stock_acc.id, "debit": cost, "credit": 0},
                     {"account_id": adj_acc.id, "debit": 0, "credit": cost}]
            desc = f"تسوية مخزون — زيادة {m.reference or m.id}"
        else:
            lines = [{"account_id": adj_acc.id, "debit": cost, "credit": 0},
                     {"account_id": stock_acc.id, "debit": 0, "credit": cost}]
            desc = f"تسوية مخزون — نقصان {m.reference or m.id}"
    else:
        return  # receipt: لا قيد تلقائي
    try:
        entry = _ps.create_entry(
            {"tenant_id": m.tenant_id, "entity_id": m.entity_id, "journal_id": journal.id,
             "entry_type": "source", "document_date": m.move_date, "posting_date": m.move_date,
             "description": desc, "source_module": "inventory",
             "source_event_key": f"inventory.move.{m.id}.gl.v1"},
            lines, actor_id=actor_id)
        _ps.post_entry(entry.id, actor_id)
        m.journal_entry_id = entry.id
    except Exception:
        # لا نفشل الحركة المخزنية بسبب خطأ قيد — يُسجَّل ويُترك للمراجعة
        import logging
        logging.getLogger(__name__).warning("inventory move %s GL posting failed", m.id, exc_info=True)


@bp.get("/quants")
@jwt_required()
def list_quants():
    q = db.session.query(StockQuant).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("product_id"):
        q = q.filter_by(product_id=uuid.UUID(str(request.args["product_id"])))
    if request.args.get("location_id"):
        q = q.filter_by(location_id=uuid.UUID(str(request.args["location_id"])))
    rows = q.limit(200).all()
    out = []
    for x in rows:
        prod = db.session.get(Product, x.product_id)
        loc = db.session.get(Location, x.location_id)
        out.append({"product_id": str(x.product_id), "product_code": prod.code if prod else "?",
                    "location_id": str(x.location_id), "location_code": loc.code if loc else "?",
                    "qty": float(x.qty), "reserved_qty": float(x.reserved_qty),
                    "available": float(x.qty) - float(x.reserved_qty)})
    return jsonify({"data": out})


def _dump_count(c):
    return {"id": str(c.id), "doc_number": c.doc_number,
            "warehouse_id": str(c.warehouse_id),
            "count_date": c.count_date.isoformat(), "status": c.status,
            "notes": c.notes}


@bp.get("/counts")
@jwt_required()
def list_counts():
    from ...models.product import StockCount
    rows = db.session.query(StockCount).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(StockCount.count_date.desc()).limit(50).all()
    return jsonify({"data": [_dump_count(c) for c in rows]})


@bp.post("/counts")
@jwt_required()
def create_count():
    denied = _deny()
    if denied:
        return denied
    from ...services import count_service
    data = request.get_json(force=True)
    try:
        c = count_service.create_count(
            tenant_id=g.tenant_id, entity_id=data["entity_id"],
            warehouse_id=data["warehouse_id"],
            count_date=date.fromisoformat(data["count_date"]) if data.get("count_date") else None,
            notes=data.get("notes"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump_count(c)}), 201


@bp.get("/counts/<uuid:count_id>")
@jwt_required()
def get_count(count_id):
    from ...models.product import StockCount
    from ...services import count_service
    c = db.session.get(StockCount, count_id)
    if c is None or c.is_deleted or str(c.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    d = _dump_count(c)
    d["lines"] = count_service.diff_report(count_id)
    return jsonify({"data": d})


@bp.post("/counts/<uuid:count_id>/<action>")
@jwt_required()
def count_action(count_id, action):
    denied = _deny()
    if denied:
        return denied
    from ...services import count_service
    from ...models.product import StockCount
    me = uuid.UUID(str(get_jwt().get("sub")))
    try:
        if action == "snapshot":
            c = count_service.snapshot(count_id, actor_id=me)
            return jsonify({"data": _dump_count(c)})
        if action == "start":
            c = count_service.start(count_id, actor_id=me)
            return jsonify({"data": _dump_count(c)})
        if action == "submit":
            data = request.get_json(force=True) or {}
            c = count_service.submit(count_id, items=data.get("lines", []), actor_id=me)
            return jsonify({"data": _dump_count(c)})
        if action == "approve":
            c = count_service.approve(count_id, actor_id=me)
            return jsonify({"data": _dump_count(c)})
        if action == "apply":
            result = count_service.apply(count_id, actor_id=me)
            return jsonify({"data": result})
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"error": {"code": "UNKNOWN_ACTION"}}), 400
