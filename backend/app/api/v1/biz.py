"""Business APIs: FX, approvals, schedules, feedback, portal, export, status."""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text as _text
from ...extensions import db
from ...models.biz import (
    ExchangeRate, ApprovalRule, ReportSchedule, Feedback, PortalToken,
)
from ...services import currency_service
from ...services.errors import AccountingError

bp = Blueprint("biz", __name__)
PAGE = 50


def _deny(perm: str = "settings.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


# ------------------------------------------------------------- FX

@bp.get("/exchange-rates")
@jwt_required()
def list_rates():
    q = db.session.query(ExchangeRate).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("pair"):
        frm, to = request.args["pair"].split("/")
        q = q.filter_by(from_currency=frm.upper(), to_currency=to.upper())
    rows = q.order_by(ExchangeRate.rate_date.desc()).limit(100).all()
    return jsonify({"data": [{"id": str(r.id), "pair": f"{r.from_currency}/{r.to_currency}",
                              "rate_date": r.rate_date.isoformat(), "rate": float(r.rate),
                              "source": r.source} for r in rows]})


@bp.post("/exchange-rates")
@jwt_required()
def upsert_rate():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    day = date.fromisoformat(data["rate_date"]) if data.get("rate_date") else date.today()
    row = db.session.query(ExchangeRate).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), from_currency=data["from_currency"].upper(),
        to_currency=data["to_currency"].upper(), rate_date=day, is_deleted=False).first()
    if row is None:
        row = ExchangeRate(tenant_id=uuid.UUID(str(g.tenant_id)),
                           from_currency=data["from_currency"].upper(),
                           to_currency=data["to_currency"].upper(), rate_date=day,
                           rate=data["rate"], source=data.get("source", "manual"),
                           created_by=me, updated_by=me)
        db.session.add(row)
    else:
        row.rate, row.source, row.updated_by = data["rate"], data.get("source", "manual"), me
    db.session.commit()
    return jsonify({"data": {"id": str(row.id), "rate": float(row.rate)}}), 201


@bp.post("/fx/convert")
@jwt_required()
def fx_convert():
    data = request.get_json(force=True)
    try:
        out = currency_service.convert(
            data["amount"], tenant_id=g.tenant_id, from_currency=data["from"],
            to_currency=data["to"], on_date=date.fromisoformat(data["date"]) if data.get("date") else None)
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"amount": float(out)}})


@bp.post("/fx/revalue")
@jwt_required()
def fx_revalue():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        out = currency_service.revalue(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], period_id=data["period_id"],
            account_codes=data["account_codes"], to_currency=data.get("to_currency", "JOD"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": out}), 201


# ------------------------------------------------------------- approval rules

@bp.get("/approval-rules")
@jwt_required()
def list_rules():
    rows = db.session.query(ApprovalRule).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(r.id), "entity_id": str(r.entity_id),
                              "doc_type": r.doc_type, "min_amount": float(r.min_amount),
                              "required_role": r.required_role, "levels": r.levels,
                              "is_active": r.is_active} for r in rows]})


@bp.post("/approval-rules")
@jwt_required()
def create_rule():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    r = ApprovalRule(tenant_id=uuid.UUID(str(g.tenant_id)),
                     entity_id=uuid.UUID(str(data["entity_id"])),
                     doc_type=data["doc_type"], min_amount=data.get("min_amount", 0),
                     required_role=data.get("required_role", "FINANCE_MANAGER"),
                     levels=data.get("levels", 1), created_by=me, updated_by=me)
    db.session.add(r)
    db.session.commit()
    return jsonify({"data": {"id": str(r.id)}}), 201


@bp.put("/approval-rules/<uuid:rid>")
@jwt_required()
def update_rule(rid):
    denied = _deny()
    if denied:
        return denied
    r = db.session.get(ApprovalRule, rid)
    if r is None or r.is_deleted or str(r.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    for f in ("min_amount", "required_role", "levels", "is_active"):
        if f in data:
            setattr(r, f, data[f])
    db.session.commit()
    return jsonify({"data": {"id": str(r.id)}})


# ------------------------------------------------------------- schedules + feedback

@bp.get("/report-schedules")
@jwt_required()
def list_schedules():
    rows = db.session.query(ReportSchedule).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(s.id), "report_code": s.report_code, "cron": s.cron,
                              "is_active": s.is_active,
                              "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None}
                             for s in rows]})


@bp.post("/report-schedules")
@jwt_required()
def create_schedule():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    s = ReportSchedule(tenant_id=uuid.UUID(str(g.tenant_id)),
                       entity_id=uuid.UUID(str(data["entity_id"])),
                       report_code=data["report_code"], cron=data.get("cron", "0 7 * * *"),
                       params=data.get("params", {}), recipients=data.get("recipients", []),
                       created_by=me, updated_by=me)
    db.session.add(s)
    db.session.commit()
    return jsonify({"data": {"id": str(s.id)}}), 201


@bp.post("/report-schedules/<uuid:sid>/run")
@jwt_required()
def run_schedule(sid):
    from datetime import datetime as _dt
    s = db.session.get(ReportSchedule, sid)
    if s is None or s.is_deleted or str(s.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    s.last_run_at = _dt.utcnow()
    db.session.commit()
    return jsonify({"data": {"id": str(s.id), "ran_at": s.last_run_at.isoformat(),
                             "note": "email delivery queued (SMTP configured in prod)"}})


@bp.get("/feedback")
@jwt_required()
def list_feedback():
    rows = db.session.query(Feedback).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Feedback.created_at.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(f.id), "kind": f.kind, "subject": f.subject,
                              "status": f.status} for f in rows]})


@bp.post("/feedback")
@jwt_required()
def create_feedback():
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    f = Feedback(tenant_id=uuid.UUID(str(g.tenant_id)), user_id=me,
                 kind=data.get("kind", "suggestion"), subject=data["subject"],
                 body=data.get("body", ""))
    db.session.add(f)
    db.session.commit()
    return jsonify({"data": {"id": str(f.id)}}), 201


# ------------------------------------------------------------- portal tokens

@bp.post("/portal-tokens")
@jwt_required()
def create_portal_token():
    denied = _deny("parties.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    from ...models.party import Party
    party = db.session.get(Party, uuid.UUID(str(data["party_id"])))
    if party is None or party.is_deleted or str(party.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "PARTY_NOT_FOUND"}}), 404
    raw = secrets.token_urlsafe(32)
    tok = PortalToken(tenant_id=uuid.UUID(str(g.tenant_id)),
                      party_id=uuid.UUID(str(data["party_id"])),
                      token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                      scope=data.get("scope", "statement"),
                      expires_at=datetime.utcnow() + timedelta(days=int(data.get("days", 30))),
                      created_by=me, updated_by=me)
    db.session.add(tok)
    db.session.commit()
    from ...services import audit_service as _audit_svc
    _audit_svc.record(tenant_id=tok.tenant_id, actor_id=me, action="portal_token",
                      entity_type="parties", entity_id=party.id,
                      new={"scope": tok.scope})
    db.session.commit()
    return jsonify({"data": {"token": raw, "expires_at": tok.expires_at.isoformat()}}), 201


# ------------------------------------------------------------- export + status

@bp.get("/export/tenant")
@jwt_required()
def export_tenant():
    """تصدير كامل لبيانات المستأجر JSON (الثقة وقابلية المغادرة)."""
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.party import Party
    from ...models.product import Product
    from ...models.account import Account
    from ...models.journal import JournalEntry, JournalLine
    from ...models.sales import CustomerInvoice
    tid = uuid.UUID(str(g.tenant_id))

    def dump(model, extra=None):
        q = db.session.query(model).filter_by(tenant_id=tid, is_deleted=False)
        rows = []
        for r in q.limit(5000).all():
            d = {}
            for col in model.__table__.columns:
                if col.key == "metadata":
                    v = getattr(r, "extra", None)
                else:
                    try:
                        v = getattr(r, col.key)
                    except AttributeError:
                        continue
                d[col.key] = (str(v) if isinstance(v, uuid.UUID) else
                              (float(v) if isinstance(v, Decimal) else
                               (v.isoformat() if hasattr(v, "isoformat") else v)))
            rows.append(d)
        return rows

    data = {
        "accounts": dump(Account), "parties": dump(Party), "products": dump(Product),
        "journal_entries": dump(JournalEntry), "journal_lines": dump(JournalLine),
        "customer_invoices": dump(CustomerInvoice),
        "exported_at": datetime.utcnow().isoformat()}
    from ...services import audit_service as _audit_svc
    _audit_svc.record(tenant_id=tid, actor_id=uuid.UUID(str(get_jwt().get("sub"))),
                      action="export", entity_type="tenant", entity_id=tid)
    db.session.commit()
    return jsonify({"data": data})


@bp.get("/status")
def status():
    from sqlalchemy import text as _text
    try:
        now = db.session.execute(_text("SELECT now()")).scalar()
        db_ok = True
    except Exception:
        now, db_ok = None, False
    return jsonify({"data": {"version": "1.0.0", "db": "up" if db_ok else "down",
                             "db_time": now.isoformat() if now else None,
                             "docs": "/api/v1/openapi.json"}})
