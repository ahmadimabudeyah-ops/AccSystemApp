"""Tenant provisioning + subscription lifecycle API (open provision, guarded admin ops)."""
from __future__ import annotations
import os
import uuid
from datetime import date, timedelta
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db, limiter
from ...models.tenant import Tenant, Plan, Subscription
from ...services import provisioning_service
from ...services.errors import AccountingError, ValidationError

bp = Blueprint("provisioning", __name__)


@bp.post("/tenants/provision")
@limiter.limit("5 per hour")
def provision():
    """تهيئة مؤسسة جديدة: مستأجر + مدير + كيان + سنة + دليل + تجربة 30 يومًا."""
    data = request.get_json(force=True) or {}
    try:
        result = provisioning_service.provision(
            code=data.get("code", ""), name_ar=data.get("name_ar", ""),
            admin_email=data.get("admin_email", ""), admin_password=data.get("admin_password", ""),
            country=data.get("country", "JO"))
    except (ValidationError, ValueError) as exc:
        code = getattr(exc, "code", "VALIDATION_ERROR")
        return jsonify({"error": {"code": code, "message": str(exc)}}), 422
    return jsonify({"data": result}), 201 if not result.get("existing") else 200


@bp.get("/plans")
def list_plans():
    rows = db.session.query(Plan).filter_by(is_deleted=False, is_active=True).all()
    return jsonify({"data": [{"id": str(p.id), "code": p.code, "name_ar": p.name_ar,
                              "price": float(p.price), "max_users": p.max_users,
                              "max_entities": p.max_entities} for p in rows]})


@bp.get("/subscriptions/me")
@jwt_required()
def my_subscription():
    sub = (db.session.query(Subscription)
           .filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
           .order_by(Subscription.ends_on.desc()).first())
    if sub is None:
        return jsonify({"data": None})
    plan = db.session.get(Plan, sub.plan_id)
    days_left = (sub.ends_on - date.today()).days
    return jsonify({"data": {"plan": plan.code if plan else "?", "status": sub.status,
                             "ends_on": sub.ends_on.isoformat(), "days_left": days_left,
                             "renewal_due": days_left <= 7}})


@bp.post("/subscriptions/renew")
@jwt_required()
def renew_subscription():
    allowed = get_jwt().get("permissions", [])
    if "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": "admin.*"}}), 403
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    plan = db.session.get(Plan, uuid.UUID(str(data["plan_id"])))
    if plan is None:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    months = int(data.get("months", 12))
    base = max(date.today(), (db.session.query(Subscription)
               .filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
               .order_by(Subscription.ends_on.desc()).first().ends_on
               if db.session.query(Subscription).filter_by(
                   tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).first() else date.today()))
    sub = Subscription(tenant_id=uuid.UUID(str(g.tenant_id)), plan_id=plan.id,
                       starts_on=base, ends_on=base + timedelta(days=30 * months),
                       status="active", created_by=me, updated_by=me)
    db.session.add(sub)
    db.session.commit()
    return jsonify({"data": {"ends_on": sub.ends_on.isoformat(), "status": sub.status}}), 201


@bp.post("/tenants/sweep")
def sweep_expired():
    """تعليق المنتهية (حماية بمفتاح صيانة) + تنبيهات تجديد لمن بقي 7 أيام."""
    maint_key = os.getenv("MAINTENANCE_KEY")
    if not maint_key or len(maint_key) < 16:
        return jsonify({"error": {"code": "MAINTENANCE_DISABLED"}}), 503
    if request.headers.get("X-Maintenance-Key") != maint_key:
        return jsonify({"error": {"code": "FORBIDDEN"}}), 403
    from ...models.ops import Notification
    today = date.today()
    suspended, warned = [], []
    for sub in db.session.query(Subscription).filter_by(is_deleted=False).all():
        if sub.status in ("trial", "active") and sub.ends_on < today:
            tenant = db.session.get(Tenant, sub.tenant_id)
            if tenant and tenant.status != "suspended":
                tenant.status = "suspended"
                suspended.append(tenant.code)
        elif sub.status in ("trial", "active") and (sub.ends_on - today).days <= 7:
            warned.append(str(sub.tenant_id))
            for u in db.session.execute(db.text(
                    "SELECT id FROM users WHERE tenant_id = :t AND is_deleted = FALSE"),
                    {"t": str(sub.tenant_id)}).all():
                db.session.add(Notification(
                    tenant_id=sub.tenant_id, user_id=u[0],
                    title="الاشتراك يقترب من الانتهاء",
                    body=f"ينتهي اشتراككم بتاريخ {sub.ends_on} — جددوا لتفادي الإيقاف",
                    severity="warning", link_url="/settings"))
    db.session.commit()
    return jsonify({"data": {"suspended": suspended, "warned_tenants": len(set(warned))}})
