"""Purchases API: vendor bills (auto-posting), payments, allocations."""
from __future__ import annotations
import uuid
from datetime import date, timedelta
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.purchases import VendorBill, VendorPayment
from ...services import purchases_service
from ...services import docs_service
from ...services.errors import AccountingError
from ...models.party import Party

bp = Blueprint("purchases", __name__)
PAGE = 50


def _deny(perm: str = "purchases.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


def _dump(b: VendorBill) -> dict:
    s = db.session.get(Party, b.supplier_id)
    return {"id": str(b.id), "entity_id": str(b.entity_id), "doc_number": b.doc_number,
            "supplier_id": str(b.supplier_id), "supplier_name": s.name_ar if s else "?",
            "bill_date": b.bill_date.isoformat(),
            "due_on": b.due_on.isoformat(), "currency_id": b.currency_id,
            "exchange_rate": float(b.exchange_rate or 1),
            "subtotal": float(b.subtotal), "tax_total": float(b.tax_total),
            "grand_total": float(b.grand_total),
            "paid_amount": float(b.paid_amount), "remaining_amount": float(b.remaining_amount),
            "status": b.status}


@bp.get("/bills")
@jwt_required()
def list_bills():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(VendorBill).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    rows = q.order_by(VendorBill.bill_date.desc()).offset((page - 1) * PAGE).limit(PAGE).all()
    return jsonify({"data": [_dump(b) for b in rows], "page": page})


@bp.post("/bills")
@jwt_required()
def create_bill():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        bill = purchases_service.create_bill(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], supplier_id=data["supplier_id"],
            bill_date=date.fromisoformat(data.get("bill_date", str(date.today()))),
            payment_term_days=data.get("payment_term_days", 0),
            currency_id=data.get("currency_id", "JOD"),
            exchange_rate=data.get("exchange_rate", 1),
            supplier_ref=data.get("supplier_ref"), lines=data["lines"],
            notes=data.get("notes"), actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump(bill)}), 201


@bp.get("/bills/<uuid:bill_id>")
@jwt_required()
def get_bill(bill_id):
    b = db.session.get(VendorBill, bill_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    d = _dump(b)
    d["lines"] = [{"line_number": l.line_number, "product_id": str(l.product_id),
                   "qty": float(l.qty), "unit_price": float(l.unit_price),
                   "line_total": float(l.line_total)} for l in b.lines if not l.is_deleted]
    return jsonify({"data": d})


@bp.post("/bills/<uuid:bill_id>/post")
@jwt_required()
def post_bill(bill_id):
    denied = _deny()
    if denied:
        return denied
    try:
        b = purchases_service.post_bill(bill_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump(b)})


@bp.get("/payments")
@jwt_required()
def list_payments():
    rows = db.session.query(VendorPayment).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(VendorPayment.pay_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(p.id), "doc_number": p.doc_number,
                              "amount": float(p.amount),
                              "unallocated_amount": float(p.unallocated_amount),
                              "status": p.status} for p in rows]})


@bp.post("/payments")
@jwt_required()
def create_payment():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        pay = purchases_service.create_payment(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], supplier_id=data["supplier_id"],
            pay_date=date.fromisoformat(data.get("pay_date", str(date.today()))),
            pay_method=data.get("pay_method", "bank_transfer"), amount=data["amount"],
            currency_id=data.get("currency_id", "JOD"),
            exchange_rate=data.get("exchange_rate", 1),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id), "doc_number": pay.doc_number}}), 201


@bp.post("/payments/<uuid:pay_id>/post")
@jwt_required()
def post_payment(pay_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        pay = purchases_service.post_payment(
            pay_id, cash_account_id=uuid.UUID(str(data["cash_account_id"])),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id), "status": pay.status}})


@bp.get("/payments/<uuid:pay_id>")
@jwt_required()
def get_payment(pay_id):
    pay = db.session.get(VendorPayment, pay_id)
    if pay is None or pay.is_deleted or str(pay.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(pay.id), "doc_number": pay.doc_number,
                             "code": pay.doc_number,
                             "amount": float(pay.amount),
                             "unallocated_amount": float(pay.unallocated_amount),
                             "status": pay.status}})


@bp.post("/payments/<uuid:pay_id>/allocate")
@jwt_required()
def allocate_payment(pay_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        pay = purchases_service.allocate(
            payment_id=pay_id, allocations=data["allocations"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id),
                             "unallocated_amount": float(pay.unallocated_amount)}})


# ------------------------------------------------------------- documents

@bp.get("/requests")
@jwt_required()
def list_requests():
    from ...models.docs import PurchaseRequest
    rows = db.session.query(PurchaseRequest).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(PurchaseRequest.request_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "doc_number": r.doc_number,
                              "status": r.status} for r in rows]})


@bp.post("/requests")
@jwt_required()
def create_request():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        r = docs_service.create_request(
            tenant_id=g.tenant_id, entity_id=data["entity_id"],
            reason=data.get("reason", ""), lines=data["lines"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(r.id), "doc_number": r.doc_number}}), 201


@bp.post("/requests/<uuid:req_id>/approve")
@jwt_required()
def approve_request(req_id):
    denied = _deny()
    if denied:
        return denied
    try:
        r = docs_service.approve_request(req_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(r.id), "status": r.status}})


@bp.get("/requests/<uuid:req_id>")
@jwt_required()
def get_request(req_id):
    from ...models.docs import PurchaseRequest
    r = db.session.get(PurchaseRequest, req_id)
    if r is None or r.is_deleted or str(r.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(r.id), "doc_number": r.doc_number,
                             "status": r.status,
                             "lines": [{"qty": float(l.qty)}
                                       for l in r.lines if not l.is_deleted]}})


@bp.get("/orders")
@jwt_required()
def list_orders():
    from ...models.docs import PurchaseOrder
    rows = db.session.query(PurchaseOrder).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(PurchaseOrder.order_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(o.id), "doc_number": o.doc_number,
                              "grand_total": float(o.grand_total),
                              "status": o.status} for o in rows]})


@bp.post("/orders")
@jwt_required()
def create_order():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        o = docs_service.create_order(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], supplier_id=data["supplier_id"],
            request_id=data.get("request_id"), lines=data["lines"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(o.id), "doc_number": o.doc_number}}), 201


@bp.get("/orders/<uuid:o_id>")
@jwt_required()
def get_order(o_id):
    from ...models.docs import PurchaseOrder
    o = db.session.get(PurchaseOrder, o_id)
    if o is None or o.is_deleted or str(o.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(o.id), "doc_number": o.doc_number,
                             "grand_total": float(o.grand_total), "status": o.status,
                             "lines": [{"qty": float(l.ordered_qty),
                                        "unit_price": float(l.unit_price),
                                        "line_total": float(l.line_total)}
                                       for l in o.lines if not l.is_deleted]}})


@bp.get("/receipts")
@jwt_required()
def list_receipts():
    from ...models.docs import GoodsReceipt
    rows = db.session.query(GoodsReceipt).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(GoodsReceipt.receipt_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(x.id), "doc_number": x.doc_number,
                              "status": x.status} for x in rows]})


@bp.get("/receipts/<uuid:rec_id>")
@jwt_required()
def get_receipt(rec_id):
    from ...models.docs import GoodsReceipt
    x = db.session.get(GoodsReceipt, rec_id)
    if x is None or x.is_deleted or str(x.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(x.id), "doc_number": x.doc_number,
                             "status": x.status,
                             "lines": [{"qty": float(l.received_qty),
                                        "unit_price": float(l.unit_cost or 0),
                                        "line_total": round(float(l.received_qty) * float(l.unit_cost or 0), 3)}
                                       for l in x.lines if not l.is_deleted]}})


@bp.get("/bills/<uuid:bill_id>/match")
@jwt_required()
def match_bill(bill_id):
    """تقرير المطابقة الثلاثية: أمر/استلام مقابل الفاتورة (كمية وسعر)."""
    from ...models.docs import PurchaseOrderLine, GoodsReceiptLine, GoodsReceipt
    b = db.session.get(VendorBill, bill_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    out = []
    for bl in b.lines:
        if bl.is_deleted:
            continue
        ordered = db.session.execute(db.text(
            "SELECT COALESCE(SUM(ordered_qty),0)::float FROM purchase_order_lines "
            "WHERE product_id = :p AND is_deleted = FALSE"), {"p": bl.product_id}).scalar() or 0.0
        received = db.session.execute(db.text(
            "SELECT COALESCE(SUM(l.received_qty),0)::float FROM goods_receipt_lines l "
            "JOIN goods_receipts g ON g.id = l.receipt_id "
            "WHERE l.product_id = :p AND g.supplier_id = :s AND l.is_deleted = FALSE"),
            {"p": bl.product_id, "s": b.supplier_id}).scalar() or 0.0
        billed = float(bl.qty) if hasattr(bl, "qty") else 0.0
        out.append({"product_id": str(bl.product_id), "billed_qty": billed,
                    "ordered_qty": ordered, "received_qty": received,
                    "match": billed <= received + 0.001})
    return jsonify({"data": {"bill_id": str(b.id), "lines": out,
                             "matched": all(x["match"] for x in out)}})


@bp.post("/bills/<uuid:bill_id>/match/confirm")
@jwt_required()
def confirm_match(bill_id):
    """اعتماد المطابقة الثلاثية: تُسجل فقط عند تطابق الكميات المفوترة مع المستلمة."""
    from ...models.purchases import BillMatch
    denied = _deny()
    if denied:
        return denied
    b = db.session.get(VendorBill, bill_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    me = uuid.UUID(str(get_jwt().get("sub")))
    out = []
    for bl in b.lines:
        if bl.is_deleted:
            continue
        ordered = db.session.execute(db.text(
            "SELECT COALESCE(SUM(ordered_qty),0)::float FROM purchase_order_lines "
            "WHERE product_id = :p AND is_deleted = FALSE"), {"p": bl.product_id}).scalar() or 0.0
        received = db.session.execute(db.text(
            "SELECT COALESCE(SUM(l.received_qty),0)::float FROM goods_receipt_lines l "
            "JOIN goods_receipts g ON g.id = l.receipt_id "
            "WHERE l.product_id = :p AND g.supplier_id = :s AND l.is_deleted = FALSE"),
            {"p": bl.product_id, "s": b.supplier_id}).scalar() or 0.0
        billed = float(bl.qty)
        out.append({"product_id": str(bl.product_id), "billed_qty": billed,
                    "ordered_qty": ordered, "received_qty": received,
                    "match": billed <= received + 0.001})
    matched = all(x["match"] for x in out)
    if not matched:
        return jsonify({"error": {"code": "MATCH_FAILED", "details": out}}), 409
    rec = BillMatch(tenant_id=b.tenant_id, entity_id=b.entity_id, bill_id=b.id,
                    matched=True, details=out, matched_by=me,
                    created_by=me, updated_by=me)
    db.session.add(rec)
    db.session.commit()
    return jsonify({"data": {"bill_id": str(b.id), "matched": True,
                             "match_id": str(rec.id)}}), 201


@bp.get("/returns")
@jwt_required()
def list_vendor_returns():
    from ...models.ops import VendorReturn
    rows = db.session.query(VendorReturn).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(VendorReturn.return_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "doc_number": r.doc_number,
                              "total_amount": float(r.total_amount),
                              "status": r.status} for r in rows]})


@bp.post("/returns")
@jwt_required()
def create_vendor_return():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    from ...services import ops_service
    try:
        ret = ops_service.create_vendor_return(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], supplier_id=data["supplier_id"],
            bill_id=data.get("bill_id"),
            return_date=date.fromisoformat(data["return_date"]) if data.get("return_date") else None,
            reason=data.get("reason", ""), warehouse_id=data.get("warehouse_id"),
            lines=data["lines"], actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(ret.id), "doc_number": ret.doc_number}}), 201


@bp.post("/returns/<uuid:ret_id>/post")
@jwt_required()
def post_vendor_return(ret_id):
    denied = _deny()
    if denied:
        return denied
    from ...services import ops_service
    try:
        ret = ops_service.post_vendor_return(ret_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(ret.id), "status": ret.status}})


@bp.get("/returns/<uuid:ret_id>")
@jwt_required()
def get_vendor_return(ret_id):
    from ...models.ops import VendorReturn
    ret = db.session.get(VendorReturn, ret_id)
    if ret is None or ret.is_deleted or str(ret.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    s = db.session.get(Party, ret.supplier_id)
    return jsonify({"data": {"id": str(ret.id), "doc_number": ret.doc_number,
                             "supplier_id": str(ret.supplier_id),
                             "supplier_name": s.name_ar if s else "?",
                             "total_amount": float(ret.total_amount), "status": ret.status,
                             "lines": [{"description": "",
                                        "qty": float(l.returned_qty), "unit_price": float(l.unit_price),
                                        "line_total": float(l.line_total)}
                                       for l in ret.lines if not l.is_deleted]}})


@bp.post("/receipts")
@jwt_required()
def create_receipt():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        x = docs_service.create_receipt(
            order_id=data.get("order_id"), tenant_id=g.tenant_id,
            entity_id=data.get("entity_id"), supplier_id=data.get("supplier_id"),
            warehouse_id=data["warehouse_id"], lines=data.get("lines"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(x.id), "doc_number": x.doc_number}}), 201


@bp.post("/receipts/<uuid:rec_id>/confirm")
@jwt_required()
def confirm_receipt(rec_id):
    denied = _deny()
    if denied:
        return denied
    try:
        x = docs_service.confirm_receipt(rec_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(x.id), "status": x.status}})


# ------------------------------------------------------------- purchase agreements

@bp.get("/agreements")
@jwt_required()
def list_agreements():
    from ...models.addons import PurchaseAgreement
    rows = db.session.query(PurchaseAgreement).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(PurchaseAgreement.created_at.desc()).limit(PAGE).all()
    out = []
    for a in rows:
        supplier = db.session.get(Party, a.supplier_id)
        total = sum(float(l.qty) * float(l.unit_price)
                    for l in a.lines if not l.is_deleted)
        out.append({"id": str(a.id), "code": a.doc_number,
                    "doc_number": a.doc_number,
                    "supplier_id": str(a.supplier_id),
                    "supplier_name": supplier.name_ar if supplier else "?",
                    "total_amount": total, "status": a.status,
                    "start_date": a.start_on.isoformat() if a.start_on else None,
                    "end_date": a.ends_on.isoformat() if a.ends_on else None})
    return jsonify({"data": out})


@bp.post("/agreements")
@jwt_required()
def create_agreement():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    from ...models.addons import PurchaseAgreement, PurchaseAgreementLine
    from ...services import sequence_service
    tenant_id = uuid.UUID(str(g.tenant_id))
    entity_id = uuid.UUID(str(data["entity_id"]))
    supplier_id = uuid.UUID(str(data["supplier_id"]))
    lines_in = data.get("lines") or []
    if not lines_in and data.get("product_id"):
        lines_in = [{"product_id": data["product_id"],
                     "qty": data.get("qty", 1),
                     "unit_price": data.get("unit_price")}]
    if not lines_in:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "at least one line is required"}}), 422
    for l in lines_in:
        if not l.get("product_id") or l.get("unit_price") is None:
            return jsonify({"error": {"code": "VALIDATION",
                                      "message": "product_id and unit_price are required"}}), 422
    number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id,
                                              doctype="purchase_agreement", year=date.today().year)
    start_on = (date.fromisoformat(data["start_date"])
                if data.get("start_date") else date.today())
    ends_on = (date.fromisoformat(data["end_date"])
               if data.get("end_date") else start_on + timedelta(days=365))
    me = uuid.UUID(str(get_jwt().get("sub")))
    agr = PurchaseAgreement(tenant_id=tenant_id, entity_id=entity_id,
                            doc_number=number, supplier_id=supplier_id,
                            start_on=start_on, ends_on=ends_on, status="draft",
                            notes=data.get("notes"), created_by=me, updated_by=me)
    db.session.add(agr)
    db.session.flush()
    for i, l in enumerate(lines_in, 1):
        db.session.add(PurchaseAgreementLine(
            tenant_id=tenant_id, agreement_id=agr.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])),
            qty=l.get("qty", 1), unit_price=l["unit_price"],
            created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": {"id": str(agr.id), "code": agr.doc_number}}), 201


@bp.get("/agreements/<uuid:agr_id>")
@jwt_required()
def get_agreement(agr_id):
    from ...models.addons import PurchaseAgreement
    agr = db.session.get(PurchaseAgreement, agr_id)
    if agr is None or agr.is_deleted or str(agr.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.product import Product
    pids = {l.product_id for l in agr.lines if not l.is_deleted and l.product_id}
    pmap = {}
    if pids:
        for p in db.session.query(Product).filter(Product.id.in_(pids)).all():
            pmap[str(p.id)] = {"code": p.code, "name_ar": p.name_ar}
    supplier = db.session.get(Party, agr.supplier_id)
    total = sum(float(l.qty) * float(l.unit_price)
                for l in agr.lines if not l.is_deleted)
    return jsonify({"data": {"id": str(agr.id), "code": agr.doc_number,
                             "doc_number": agr.doc_number,
                             "supplier_id": str(agr.supplier_id),
                             "supplier_name": supplier.name_ar if supplier else "?",
                             "start_date": agr.start_on.isoformat() if agr.start_on else None,
                             "end_date": agr.ends_on.isoformat() if agr.ends_on else None,
                             "subtotal": total, "tax_total": 0,
                             "grand_total": total, "total_amount": total,
                             "status": agr.status, "notes": agr.notes,
                             "lines": [{"product_id": str(l.product_id) if l.product_id else None,
                                        "product_code": (pmap.get(str(l.product_id)) or {}).get("code"),
                                        "product_name": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                                        "qty": float(l.qty), "unit_price": float(l.unit_price),
                                        "line_total": float(l.qty) * float(l.unit_price)}
                                       for l in agr.lines if not l.is_deleted]}})


@bp.post("/agreements/<uuid:agr_id>/confirm")
@jwt_required()
def confirm_agreement(agr_id):
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import PurchaseAgreement
    agr = db.session.get(PurchaseAgreement, agr_id)
    if agr is None or agr.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if agr.status == "confirmed":
        return jsonify({"data": {"id": str(agr.id), "status": agr.status}})
    if agr.status != "draft":
        return jsonify({"error": {"code": "BAD_STATE",
                                  "message": f"Cannot confirm from {agr.status}"}}), 409
    agr.status = "confirmed"
    db.session.commit()
    return jsonify({"data": {"id": str(agr.id), "status": agr.status}})
