"""Accounts API: CRUD + tree + soft delete.

GET    /api/v1/accounts            list (filter/search/paginate)
POST   /api/v1/accounts            create
GET    /api/v1/accounts/tree       hierarchy (materialized path)
GET    /api/v1/accounts/<id>       detail
PUT    /api/v1/accounts/<id>       update (blocked when posted lines exist -> 409)
DELETE /api/v1/accounts/<id>       soft delete
"""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.account import Account
from ...services.errors import NotFoundError, BadStateError

bp = Blueprint("accounts", __name__)
PAGE_SIZE = 50


def _deny(perm: str):
    claims = get_jwt()
    allowed = claims.get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _dump(a: Account) -> dict:
    return {"id": str(a.id), "entity_id": str(a.entity_id), "code": a.code,
            "name_ar": a.name_ar, "name_en": a.name_en, "parent_id": str(a.parent_id) if a.parent_id else None,
            "account_type": a.account_type, "control_type": a.control_type,
            "is_postable": a.is_postable, "normal_balance": a.normal_balance,
            "allow_manual": a.allow_manual, "reconcilable": a.reconcilable,
            "require_partner": a.require_partner,
            "status": a.status, "version": a.version}


@bp.get("")
@jwt_required()
def list_accounts():
    q = db.session.query(Account).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("type"):
        q = q.filter_by(account_type=request.args["type"])
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((Account.code.like(like)) | (Account.name_ar.like(like)))
    page = max(int(request.args.get("page", 1)), 1)
    rows = q.order_by(Account.code).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return jsonify({"data": [_dump(a) for a in rows], "page": page, "page_size": PAGE_SIZE})


@bp.get("/tree")
@jwt_required()
def tree():
    entity_id = request.args.get("entity_id")
    entity_id = request.args.get("entity_id")
    q = db.session.query(Account).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if entity_id:
        q = q.filter_by(entity_id=uuid.UUID(str(entity_id)))
    accounts = q.order_by(Account.code).all()
    by_parent: dict[str | None, list] = {}
    for a in accounts:
        by_parent.setdefault(str(a.parent_id) if a.parent_id else None, []).append(_dump(a))

    def nest(pid):
        return [{**n, "children": nest(n["id"])} for n in by_parent.get(pid, [])]

    return jsonify(nest(None))


@bp.post("")
@jwt_required()
def create_account():
    denied = _deny("accounts.create")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    acc = Account(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                  code=data["code"],
                  name_ar=data["name_ar"], name_en=data.get("name_en"),
                  parent_id=uuid.UUID(str(data["parent_id"])) if data.get("parent_id") else None,
                  account_type=data["account_type"],
                  control_type=data.get("control_type", "general"),
                  is_postable=data.get("is_postable", True),
                  normal_balance=data["normal_balance"],
                  allow_manual=data.get("allow_manual", True),
                  reconcilable=data.get("reconcilable", False),
                  require_partner=data.get("require_partner", False),
                  status="active",
                  created_by=me, updated_by=me)
    db.session.add(acc)
    db.session.commit()
    return jsonify({"data": _dump(acc)}), 201


@bp.get("/<uuid:acc_id>")
@jwt_required()
def get_account(acc_id):
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted or str(acc.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": _dump(acc)})


@bp.put("/<uuid:acc_id>")
@jwt_required()
def update_account(acc_id):
    denied = _deny("accounts.update")
    if denied:
        return denied
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    if str(data.get("version", acc.version)) != str(acc.version):
        return jsonify({"error": {"code": "CONCURRENT_MODIFICATION"}}), 409
    for field in ("name_ar", "name_en", "allow_manual", "reconcilable", "currency_id", "status"):
        if field in data:
            setattr(acc, field, data[field])
    db.session.commit()
    return jsonify({"data": _dump(acc)})


@bp.delete("/<uuid:acc_id>")
@jwt_required()
def delete_account(acc_id):
    denied = _deny("accounts.delete")
    if denied:
        return denied
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.journal import JournalLine
    used = db.session.query(JournalLine).filter_by(account_id=acc.id, is_deleted=False).first()
    if used:
        return jsonify({"error": {"code": "ACCOUNT_HAS_MOVEMENTS"}}), 409
    acc.is_deleted = True
    db.session.commit()
    return jsonify({"data": {"id": str(acc.id), "deleted": True}})
