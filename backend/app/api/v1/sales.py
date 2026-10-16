"""Sales API: invoices (auto-posting), payments, allocations, terms, e-invoicing queue."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text as _text
from ...extensions import db
from ...models.sales import CustomerInvoice, CustomerPayment, PaymentTerm
from ...services import sales_service
from ...services import credit_service
from ...services import docs_service
from ...services.errors import AccountingError
from ...models.product import Product

bp = Blueprint("sales", __name__)
PAGE = 50


def _deny(perm: str = "sales.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


def _dump_inv(i: CustomerInvoice) -> dict:
    from ...models.party import Party
    cust = db.session.get(Party, i.customer_id)
    return {"id": str(i.id), "entity_id": str(i.entity_id), "doc_number": i.doc_number,
            "customer_id": str(i.customer_id),
            "customer_name": cust.name_ar if cust else "?",
            "invoice_date": i.invoice_date.isoformat(),
            "due_on": i.due_on.isoformat(), "currency_id": i.currency_id,
            "exchange_rate": float(i.exchange_rate or 1),
            "subtotal": float(i.subtotal),
            "tax_total": float(i.tax_total), "grand_total": float(i.grand_total),
            "paid_amount": float(i.paid_amount), "remaining_amount": float(i.remaining_amount),
            "status": i.status, "journal_entry_id": str(i.journal_entry_id) if i.journal_entry_id else None}


@bp.get("/invoices")
@jwt_required()
def list_invoices():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(CustomerInvoice).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("customer_id"):
        q = q.filter_by(customer_id=uuid.UUID(str(request.args["customer_id"])))
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    rows = q.order_by(CustomerInvoice.invoice_date.desc()).offset((page - 1) * PAGE).limit(PAGE).all()
    return jsonify({"data": [_dump_inv(i) for i in rows], "page": page})


@bp.post("/invoices")
@jwt_required()
def create_invoice():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        inv = sales_service.create_invoice(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            invoice_date=date.fromisoformat(data.get("invoice_date", str(date.today()))),
            payment_term_days=data.get("payment_term_days", 0),
            currency_id=data.get("currency_id", "JOD"),
            exchange_rate=data.get("exchange_rate", 1), lines=data["lines"],
            reference=data.get("reference"), notes=data.get("notes"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump_inv(inv)}), 201


@bp.get("/invoices/<uuid:inv_id>")
@jwt_required()
def get_invoice(inv_id):
    inv = db.session.get(CustomerInvoice, inv_id)
    if inv is None or inv.is_deleted or str(inv.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    d = _dump_inv(inv)
    pids = {l.product_id for l in inv.lines if not l.is_deleted and l.product_id}
    pmap = {}
    if pids:
        from ...models.product import Product
        for p in db.session.query(Product).filter(Product.id.in_(pids)).all():
            pmap[str(p.id)] = {"code": p.code, "name_ar": p.name_ar}
    d["lines"] = [{"line_number": l.line_number, "product_id": str(l.product_id) if l.product_id else None,
                   "product_code": (pmap.get(str(l.product_id)) or {}).get("code"),
                   "product_name": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                   "description": l.description, "qty": float(l.qty),
                   "unit_price": float(l.unit_price), "line_total": float(l.line_total)}
                  for l in inv.lines if not l.is_deleted]
    return jsonify({"data": d})


@bp.post("/invoices/<uuid:inv_id>/post")
@jwt_required()
def post_invoice(inv_id):
    denied = _deny()
    if denied:
        return denied
    try:
        inv = sales_service.post_invoice(inv_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    d = _dump_inv(inv)
    if getattr(inv, "stock_warnings", None):
        d["stock_warnings"] = inv.stock_warnings
    return jsonify({"data": d})


@bp.get("/payments")
@jwt_required()
def list_payments():
    rows = db.session.query(CustomerPayment).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(CustomerPayment.pay_date.desc()).limit(PAGE).all()
    from ...models.party import Party as _Party
    out = []
    for p in rows:
        c = db.session.get(_Party, p.customer_id)
        out.append({"id": str(p.id), "doc_number": p.doc_number,
                    "customer_name": c.name_ar if c else "?",
                    "amount": float(p.amount),
                    "allocated_amount": float(p.allocated_amount),
                    "unallocated_amount": float(p.unallocated_amount),
                    "status": p.status})
    return jsonify({"data": out})


@bp.post("/payments")
@jwt_required()
def create_payment():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        pay = sales_service.create_payment(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            pay_date=date.fromisoformat(data.get("pay_date", str(date.today()))),
            pay_method=data.get("pay_method", "cash"), amount=data["amount"],
            currency_id=data.get("currency_id", "JOD"),
            exchange_rate=data.get("exchange_rate", 1), reference=data.get("reference"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id), "doc_number": pay.doc_number,
                             "status": pay.status}}), 201


@bp.get("/payments/<uuid:pay_id>")
@jwt_required()
def get_payment(pay_id):
    pay = db.session.get(CustomerPayment, pay_id)
    if pay is None or pay.is_deleted or str(pay.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.party import Party as _Party2
    cust = db.session.get(_Party2, pay.customer_id)
    return jsonify({"data": {"id": str(pay.id), "doc_number": pay.doc_number,
                             "code": pay.doc_number,
                             "customer_name": cust.name_ar if cust else "?",
                             "amount": float(pay.amount),
                             "allocated_amount": float(pay.allocated_amount),
                             "unallocated_amount": float(pay.unallocated_amount),
                             "status": pay.status}})


@bp.post("/payments/<uuid:pay_id>/post")
@jwt_required()
def post_payment(pay_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        pay = sales_service.post_payment(
            pay_id, cash_account_id=uuid.UUID(str(data["cash_account_id"])),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))),
            journal_code=data.get("journal_code", "CASH"))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id), "status": pay.status,
                             "entry_id": str(pay.journal_entry_id)}})


@bp.post("/payments/<uuid:pay_id>/allocate")
@jwt_required()
def allocate_payment(pay_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        pay = sales_service.allocate(
            payment_id=pay_id, allocations=data["allocations"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id),
                             "allocated_amount": float(pay.allocated_amount),
                             "unallocated_amount": float(pay.unallocated_amount)}})


@bp.get("/payment-terms")
@jwt_required()
def list_terms():
    rows = db.session.query(PaymentTerm).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    if not rows:
        rows = [PaymentTerm(code=c, name_ar=n, days=d)
                for c, n, d in [("IMMEDIATE", "فوري", 0), ("NET30", "30 يوم", 30), ("NET60", "60 يوم", 60)]]
    return jsonify({"data": [{"id": str(r.id) if r.id else r.code, "code": r.code,
                              "name_ar": r.name_ar, "days": r.days} for r in rows]})


@bp.get("/einvoicing-queue")
@jwt_required()
def einvoicing_queue():
    rows = db.session.execute(_text(
        "SELECT q.id::text, q.invoice_id::text, i.doc_number, q.einv_status, q.attempts "
        "FROM einvoicing_queue q JOIN customer_invoices i ON i.id = q.invoice_id "
        "WHERE q.tenant_id = :t AND q.is_deleted = FALSE ORDER BY q.created_at DESC LIMIT 50"),
        {"t": str(g.tenant_id)}).all()
    return jsonify({"data": [{"id": r[0], "invoice_id": r[1], "doc_number": r[2],
                              "status": r[3], "attempts": r[4]} for r in rows]})


@bp.get("/credit-notes")
@jwt_required()
def list_credit_notes():
    from ...models.sales import CreditNote
    rows = db.session.query(CreditNote).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(CreditNote.note_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(n.id), "doc_number": n.doc_number,
                              "grand_total": float(n.grand_total),
                              "status": n.status} for n in rows]})


@bp.post("/credit-notes")
@jwt_required()
def create_credit_note():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        note = credit_service.create_credit_note(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            invoice_id=data.get("invoice_id"),
            note_date=date.fromisoformat(data["note_date"]) if data.get("note_date") else None,
            reason=data.get("reason", ""), lines=data["lines"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(note.id), "doc_number": note.doc_number}}), 201


@bp.post("/credit-notes/<uuid:note_id>/post")
@jwt_required()
def post_credit_note(note_id):
    denied = _deny()
    if denied:
        return denied
    try:
        note = credit_service.post_credit_note(
            note_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(note.id), "status": note.status}})


@bp.get("/credit-notes/<uuid:note_id>")
@jwt_required()
def get_credit_note(note_id):
    from ...models.sales import CreditNote
    note = db.session.get(CreditNote, note_id)
    if note is None or note.is_deleted or str(note.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.party import Party
    cust = db.session.get(Party, note.customer_id)
    pids = {l.product_id for l in note.lines if not l.is_deleted and l.product_id}
    pmap = {}
    if pids:
        from ...models.product import Product as _Prod
        for p in db.session.query(_Prod).filter(_Prod.id.in_(pids)).all():
            pmap[str(p.id)] = {"code": p.code, "name_ar": p.name_ar}
    return jsonify({"data": {"id": str(note.id), "doc_number": note.doc_number,
                             "customer_id": str(note.customer_id),
                             "customer_name": cust.name_ar if cust else "?",
                             "subtotal": float(note.subtotal),
                             "tax_total": float(note.tax_total),
                             "grand_total": float(note.grand_total), "status": note.status,
                             "lines": [{"product_id": str(l.product_id) if l.product_id else None,
                                        "product_code": (pmap.get(str(l.product_id)) or {}).get("code"),
                                        "product_name": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                                        "description": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                                        "qty": float(l.qty), "unit_price": float(l.unit_price),
                                        "discount_pct": float(l.discount_pct or 0),
                                        "line_total": float(l.line_total)}
                                       for l in note.lines if not l.is_deleted]}})


@bp.get("/returns")
@jwt_required()
def list_returns():
    from ...models.sales import CustomerReturn
    rows = db.session.query(CustomerReturn).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(CustomerReturn.return_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "doc_number": r.doc_number,
                              "total_amount": float(r.total_amount),
                              "status": r.status} for r in rows]})


@bp.post("/returns")
@jwt_required()
def create_return():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        ret = credit_service.create_return(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            invoice_id=data.get("invoice_id"),
            return_date=date.fromisoformat(data["return_date"]) if data.get("return_date") else None,
            reason=data.get("reason", ""), warehouse_id=data.get("warehouse_id"),
            lines=data["lines"], actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(ret.id), "doc_number": ret.doc_number}}), 201


@bp.post("/returns/<uuid:ret_id>/post")
@jwt_required()
def post_return(ret_id):
    denied = _deny()
    if denied:
        return denied
    try:
        ret = credit_service.post_return(ret_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(ret.id), "status": ret.status}})


@bp.get("/returns/<uuid:ret_id>")
@jwt_required()
def get_return(ret_id):
    from ...models.sales import CustomerReturn
    ret = db.session.get(CustomerReturn, ret_id)
    if ret is None or ret.is_deleted or str(ret.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.party import Party
    cust = db.session.get(Party, ret.customer_id)
    return jsonify({"data": {"id": str(ret.id), "doc_number": ret.doc_number,
                             "customer_id": str(ret.customer_id),
                             "customer_name": cust.name_ar if cust else "?",
                             "total_amount": float(ret.total_amount), "status": ret.status,
                             "lines": [{"description": l.description or "",
                                        "qty": float(l.returned_qty), "unit_price": float(l.unit_price),
                                        "line_total": float(l.line_total)}
                                       for l in ret.lines if not l.is_deleted]}})


@bp.post("/invoices/<uuid:inv_id>/dispute")
@jwt_required()
def dispute_invoice(inv_id):
    denied = _deny()
    if denied:
        return denied
    inv = db.session.get(CustomerInvoice, inv_id)
    if inv is None or inv.is_deleted or str(inv.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if inv.status not in ("posted", "partially_paid", "sent"):
        return jsonify({"error": {"code": "BAD_STATE"}}), 409
    inv.status = "disputed"
    db.session.commit()
    return jsonify({"data": {"id": str(inv.id), "status": inv.status}})


@bp.post("/invoices/<uuid:inv_id>/reverse")
@jwt_required()
def reverse_invoice(inv_id):
    """عكس فاتورة بإشعار دائن كامل مرحّل تلقائيًا."""
    denied = _deny()
    if denied:
        return denied
    inv = db.session.get(CustomerInvoice, inv_id)
    if inv is None or inv.is_deleted or str(inv.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if inv.status not in ("posted", "partially_paid"):
        return jsonify({"error": {"code": "BAD_STATE"}}), 409
    if float(inv.paid_amount) > 0.001:
        return jsonify({"error": {"code": "HAS_PAYMENTS_USE_CREDIT"}}), 409
    try:
        note = credit_service.create_credit_note(
            tenant_id=inv.tenant_id, entity_id=inv.entity_id, customer_id=inv.customer_id,
            invoice_id=inv.id, reason=f"عكس الفاتورة {inv.doc_number}",
            lines=[{"product_id": l.product_id, "qty": float(l.qty),
                    "unit_price": float(l.unit_price),
                    "discount_pct": float(l.discount_pct or 0),
                    "tax_id": l.tax_id} for l in inv.lines if not l.is_deleted],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
        note = credit_service.post_credit_note(note.id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
        inv.status = "reversed"
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(inv.id), "status": inv.status,
                             "credit_note_id": str(note.id)}}), 201


# ------------------------------------------------------------- quotations

@bp.get("/quotations")
@jwt_required()
def list_quotations():
    from ...models.docs import Quotation
    rows = db.session.query(Quotation).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Quotation.quote_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(q.id), "doc_number": q.doc_number,
                              "grand_total": float(q.grand_total),
                              "status": q.status} for q in rows]})


@bp.post("/quotations")
@jwt_required()
def create_quotation():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        q = docs_service.create_quotation(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            lines=data["lines"], valid_days=data.get("valid_days", 15),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(q.id), "doc_number": q.doc_number}}), 201


@bp.post("/quotations/<uuid:q_id>/convert")
@jwt_required()
def convert_quotation(q_id):
    denied = _deny()
    if denied:
        return denied
    try:
        o = docs_service.convert_quotation(q_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(o.id), "doc_number": o.doc_number}}), 201


@bp.get("/quotations/<uuid:q_id>")
@jwt_required()
def get_quotation(q_id):
    from ...models.docs import Quotation
    q = db.session.get(Quotation, q_id)
    if q is None or q.is_deleted or str(q.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(q.id), "doc_number": q.doc_number,
                             "subtotal": float(q.subtotal),
                             "tax_total": float(q.tax_total),
                             "grand_total": float(q.grand_total), "status": q.status,
                             "lines": [{"description": l.description,
                                        "qty": float(l.qty), "unit_price": float(l.unit_price),
                                        "line_total": float(l.line_total)}
                                       for l in q.lines if not l.is_deleted]}})


# ------------------------------------------------------------- orders & deliveries

@bp.get("/orders")
@jwt_required()
def list_orders():
    from ...models.docs import SalesOrder
    rows = db.session.query(SalesOrder).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(SalesOrder.order_date.desc()).limit(PAGE).all()
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
        if data.get("quotation_id"):
            o = docs_service.convert_quotation(
                uuid.UUID(str(data["quotation_id"])),
                actor_id=uuid.UUID(str(get_jwt().get("sub"))))
        else:
            raise AccountingError("ORDER_NEEDS_QUOTATION")
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(o.id), "doc_number": o.doc_number}}), 201


@bp.get("/orders/<uuid:o_id>")
@jwt_required()
def get_order(o_id):
    from ...models.docs import SalesOrder
    o = db.session.get(SalesOrder, o_id)
    if o is None or o.is_deleted or str(o.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(o.id), "doc_number": o.doc_number,
                             "grand_total": float(o.grand_total), "status": o.status,
                             "lines": [{"product_id": str(l.product_id),
                                         "ordered_qty": float(l.ordered_qty),
                                         "delivered_qty": float(l.delivered_qty),
                                         "unit_price": float(l.unit_price),
                                         "line_total": float(l.line_total)}
                                        for l in o.lines if not l.is_deleted]}})


@bp.get("/deliveries")
@jwt_required()
def list_deliveries():
    from ...models.docs import Delivery
    rows = db.session.query(Delivery).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Delivery.delivery_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(d.id), "doc_number": d.doc_number,
                              "status": d.status} for d in rows]})


@bp.post("/deliveries")
@jwt_required()
def create_delivery():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        d = docs_service.create_delivery(
            order_id=data["order_id"], warehouse_id=data["warehouse_id"],
            lines=data.get("lines"), actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(d.id), "doc_number": d.doc_number}}), 201


@bp.post("/deliveries/<uuid:d_id>/confirm")
@jwt_required()
def confirm_delivery(d_id):
    denied = _deny()
    if denied:
        return denied
    try:
        d = docs_service.confirm_delivery(d_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(d.id), "status": d.status}})


@bp.get("/deliveries/<uuid:d_id>")
@jwt_required()
def get_delivery(d_id):
    from ...models.docs import Delivery
    d = db.session.get(Delivery, d_id)
    if d is None or d.is_deleted or str(d.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(d.id), "doc_number": d.doc_number,
                             "status": d.status,
                             "lines": [{"qty": float(l.requested_qty),
                                        "delivered_qty": float(l.delivered_qty)}
                                       for l in d.lines if not l.is_deleted]}})


@bp.post("/orders/<uuid:o_id>/invoice")
@jwt_required()
def invoice_from_order(o_id):
    """فوترة أمر بيع: إنشاء فاتورة من الكميات غير المفوترة."""
    from ...models.docs import SalesOrder
    denied = _deny()
    if denied:
        return denied
    o = db.session.get(SalesOrder, o_id)
    if o is None or o.is_deleted or str(o.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(silent=True) or {}
    try:
        lines = []
        for l in o.lines:
            if l.is_deleted:
                continue
            qty = float(l.ordered_qty) - float(l.invoiced_qty)
            if qty <= 0.001:
                continue
            prod = db.session.get(Product, l.product_id)
            lines.append({"product_id": l.product_id, "qty": qty,
                          "unit_price": float(l.unit_price),
                          "discount_pct": float(l.discount_pct or 0),
                          "tax_id": data.get("tax_id")})
        if not lines:
            return jsonify({"error": {"code": "NOTHING_TO_INVOICE"}}), 409
        inv = sales_service.create_invoice(
            tenant_id=o.tenant_id, entity_id=o.entity_id, customer_id=o.customer_id,
            invoice_date=date.fromisoformat(data.get("invoice_date", str(date.today()))),
            payment_term_days=data.get("payment_term_days", 0),
            currency_id="JOD",
            lines=lines, reference=o.doc_number,
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
        for l in o.lines:
            if not l.is_deleted:
                l.invoiced_qty = float(l.ordered_qty)
        o.status = "fully_invoiced"
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(inv.id), "doc_number": inv.doc_number}}), 201


@bp.post("/einvoicing/process")
@jwt_required()
def process_einvoicing():
    denied = _deny("sales.manage")
    if denied:
        return denied
    from ...services import jofotara_service
    out = jofotara_service.process_queue(tenant_id=g.tenant_id)
    return jsonify({"data": {"processed": out}})


# ------------------------------------------------------------- debit notes

@bp.get("/debit-notes")
@jwt_required()
def list_debit_notes():
    from ...models.addons import DebitNote
    rows = db.session.query(DebitNote).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(DebitNote.note_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(n.id), "doc_number": n.doc_number,
                              "grand_total": float(n.grand_total),
                              "status": n.status} for n in rows]})


@bp.post("/debit-notes")
@jwt_required()
def create_debit_note():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        note = credit_service.create_debit_note(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], customer_id=data["customer_id"],
            note_date=date.fromisoformat(data["note_date"]) if data.get("note_date") else None,
            reason=data.get("reason", ""), currency_id=data.get("currency_id", "JOD"),
            lines=data["lines"], actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(note.id), "doc_number": note.doc_number}}), 201


@bp.get("/debit-notes/<uuid:note_id>")
@jwt_required()
def get_debit_note(note_id):
    from ...models.addons import DebitNote
    note = db.session.get(DebitNote, note_id)
    if note is None or note.is_deleted or str(note.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.party import Party
    cust = db.session.get(Party, note.customer_id)
    pids = {l.product_id for l in note.lines if not l.is_deleted and l.product_id}
    pmap = {}
    if pids:
        for p in db.session.query(Product).filter(Product.id.in_(pids)).all():
            pmap[str(p.id)] = {"code": p.code, "name_ar": p.name_ar}
    return jsonify({"data": {"id": str(note.id), "doc_number": note.doc_number,
                             "code": note.doc_number,
                             "customer_name": cust.name_ar if cust else "?",
                             "subtotal": float(note.subtotal),
                             "tax_total": float(note.tax_total),
                             "grand_total": float(note.grand_total), "status": note.status,
                             "lines": [{"product_id": str(l.product_id) if l.product_id else None,
                                        "product_code": (pmap.get(str(l.product_id)) or {}).get("code"),
                                        "product_name": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                                        "description": (pmap.get(str(l.product_id)) or {}).get("name_ar"),
                                        "qty": float(l.qty), "unit_price": float(l.unit_price),
                                        "line_total": float(l.line_total)}
                                       for l in note.lines if not l.is_deleted]}})


@bp.post("/debit-notes/<uuid:note_id>/post")
@jwt_required()
def post_debit_note(note_id):
    denied = _deny()
    if denied:
        return denied
    try:
        note = credit_service.post_debit_note(note_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(note.id), "status": note.status}})
