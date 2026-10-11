"""Settings API: general/company tenant settings + own profile + roles.

GET/PUT  /api/v1/settings/general   (currency, timezone)
GET/PUT  /api/v1/settings/company    (name_ar, tax_id)
GET/PUT  /api/v1/users/me            (full_name, email)
POST     /api/v1/roles               (code, name_ar)
"""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.tenant import Tenant
from ...models.user import User, Role
from ...services.errors import AccountingError

bp = Blueprint("settings", __name__)


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _tenant():
    return db.session.query(Tenant).filter_by(
        id=uuid.UUID(str(g.tenant_id)), is_deleted=False).first()


@bp.get("/settings/general")
@jwt_required()
def get_general():
    denied = _deny("settings.manage")
    if denied:
        return denied
    t = _tenant()
    if t is None:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"currency": t.default_currency, "timezone": t.timezone}})


@bp.put("/settings/general")
@jwt_required()
def put_general():
    denied = _deny("settings.manage")
    if denied:
        return denied
    t = _tenant()
    if t is None:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True) or {}
    if data.get("currency"):
        t.default_currency = str(data["currency"]).upper()[:3]
    if data.get("timezone"):
        t.timezone = str(data["timezone"])[:64]
    db.session.commit()
    return jsonify({"data": {"currency": t.default_currency, "timezone": t.timezone}})


@bp.get("/settings/company")
@jwt_required()
def get_company():
    denied = _deny("settings.manage")
    if denied:
        return denied
    t = _tenant()
    if t is None:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"name_ar": t.name_ar, "tax_id": t.tax_id}})


@bp.put("/settings/company")
@jwt_required()
def put_company():
    denied = _deny("settings.manage")
    if denied:
        return denied
    t = _tenant()
    if t is None:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True) or {}
    if not str(data.get("name_ar", "")).strip():
        return jsonify({"error": {"code": "NAME_REQUIRED"}}), 400
    t.name_ar = str(data["name_ar"]).strip()
    t.tax_id = str(data.get("tax_id") or "").strip() or None
    db.session.commit()
    return jsonify({"data": {"name_ar": t.name_ar, "tax_id": t.tax_id}})


@bp.get("/users/me")
@jwt_required()
def get_me():
    u = db.session.get(User, uuid.UUID(str(get_jwt().get("sub"))))
    if u is None or u.is_deleted or str(u.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(u.id), "username": u.username,
                             "email": u.email, "full_name": u.full_name}})


@bp.put("/users/me")
@jwt_required()
def put_me():
    u = db.session.get(User, uuid.UUID(str(get_jwt().get("sub"))))
    if u is None or u.is_deleted or str(u.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True) or {}
    if data.get("email"):
        u.email = str(data["email"]).strip().lower()
    if "full_name" in data:
        u.full_name = str(data["full_name"] or "").strip() or None
    u.updated_by = u.id
    db.session.commit()
    return jsonify({"data": {"id": str(u.id), "username": u.username,
                             "email": u.email, "full_name": u.full_name}})


@bp.post("/roles")
@jwt_required()
def create_role():
    denied = _deny("users.create")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    code = str(data.get("code", "")).strip().upper()
    name_ar = str(data.get("name_ar", "")).strip()
    if not code or not name_ar:
        return jsonify({"error": {"code": "CODE_AND_NAME_REQUIRED"}}), 400
    exists = db.session.query(Role).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), code=code, is_deleted=False).first()
    if exists:
        return jsonify({"error": {"code": "ROLE_EXISTS"}}), 409
    r = Role(tenant_id=uuid.UUID(str(g.tenant_id)), code=code, name_ar=name_ar,
             created_by=me, updated_by=me)
    db.session.add(r)
    db.session.commit()
    return jsonify({"data": {"id": str(r.id), "code": r.code, "name_ar": r.name_ar}}), 201


@bp.get("/roles/<uuid:role_id>")
@jwt_required()
def get_role(role_id):
    denied = _deny("users.view")
    if denied:
        return denied
    r = db.session.get(Role, role_id)
    if r is None or r.is_deleted or str(r.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(r.id), "code": r.code, "name_ar": r.name_ar}})


@bp.put("/roles/<uuid:role_id>")
@jwt_required()
def update_role(role_id):
    denied = _deny("users.create")
    if denied:
        return denied
    r = db.session.get(Role, role_id)
    if r is None or r.is_deleted or str(r.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if r.is_system:
        return jsonify({"error": {"code": "SYSTEM_ROLE_LOCKED"}}), 409
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    if data.get("name_ar"):
        r.name_ar = str(data["name_ar"]).strip()
    r.updated_by = me
    db.session.commit()
    return jsonify({"data": {"id": str(r.id), "code": r.code, "name_ar": r.name_ar}})
