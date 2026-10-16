"""Tenant + entity read endpoints (scoped by RLS). Uniform {"data": [...]} schema."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.tenant import Tenant
from ...models.entity import Entity, Branch

bp = Blueprint("tenants", __name__)


def _deny(perm: str = "admin.*"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _same_tenant(url_tenant_id) -> bool:
    from flask import g as _g
    return str(url_tenant_id) == str(_g.tenant_id)


def _own_entity(entity_id) -> bool:
    from flask import g as _g
    e = db.session.get(Entity, entity_id)
    return e is not None and not e.is_deleted and str(e.tenant_id) == str(_g.tenant_id)


@bp.get("")
@jwt_required()
def list_tenants():
    # قائمة المستأجرين حساسة (معرفات وأسماء الغير) — للإدارة فقط.
    denied = _deny("admin.*")
    if denied:
        return denied
    rows = db.session.query(Tenant).filter_by(is_deleted=False).all()
    return jsonify({"data": [{"id": str(t.id), "code": t.code, "name_ar": t.name_ar} for t in rows]})


@bp.get("/<uuid:tenant_id>/entities")
@jwt_required()
def list_entities(tenant_id):
    if not _same_tenant(tenant_id):
        denied = _deny("admin.*")
        if denied:
            return denied
    rows = db.session.query(Entity).filter_by(tenant_id=tenant_id, is_deleted=False).all()
    return jsonify({"data": [{"id": str(e.id), "code": e.code, "name_ar": e.name_ar,
                              "functional_currency": e.functional_currency} for e in rows]})


@bp.get("/entities/<uuid:entity_id>/branches")
@jwt_required()
def list_branches(entity_id):
    if not _own_entity(entity_id):
        denied = _deny("admin.*")
        if denied:
            return denied
    rows = db.session.query(Branch).filter_by(entity_id=entity_id, is_deleted=False).all()
    return jsonify({"data": [{"id": str(b.id), "code": b.code, "name_ar": b.name_ar} for b in rows]})


@bp.get("/fiscal-years")
@jwt_required()
def list_fiscal_years():
    from ...models.entity import FiscalYear
    from flask import request, g as _g
    q = db.session.query(FiscalYear).join(Entity, Entity.id == FiscalYear.entity_id).filter(
        FiscalYear.is_deleted.is_(False), Entity.tenant_id == _g.tenant_id)
    if request.args.get("entity_id"):
        import uuid as _uuid
        eid = _uuid.UUID(str(request.args["entity_id"]))
        if not _own_entity(eid):
            denied = _deny("admin.*")
            if denied:
                return denied
        q = q.filter_by(entity_id=eid)
    rows = q.order_by(FiscalYear.starts_on.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(f.id), "code": f.code, "status": f.status,
                              "starts_on": f.starts_on.isoformat(),
                              "ends_on": f.ends_on.isoformat()} for f in rows]})
