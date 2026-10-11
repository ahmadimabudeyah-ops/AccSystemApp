"""Users API (admin only).

GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/<id>
PUT    /api/v1/users/<id>          (is_active, role assignment)
POST   /api/v1/users/<id>/deactivate
GET    /api/v1/roles
"""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.user import User, Role, UserRole
from ...utils.security import hash_password

bp = Blueprint("users", __name__)
PAGE_SIZE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _dump(u: User) -> dict:
    roles = [str(r.role_id) for r in u.roles] if u.roles else []
    return {"id": str(u.id), "username": u.username, "email": u.email,
            "is_active": u.is_active,
            "status": "active" if u.is_active else "suspended", "roles": roles}


@bp.get("/users")
@jwt_required()
def list_users():
    denied = _deny("users.view")
    if denied:
        return denied
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(User).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((User.username.like(like)) | (User.email.like(like)))
    rows = q.order_by(User.username).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return jsonify({"data": [_dump(u) for u in rows], "page": page})


@bp.post("/users")
@jwt_required()
def create_user():
    denied = _deny("users.create")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    from ...utils.security import validate_password
    try:
        validate_password(data.get("password", ""))
    except ValueError as exc:
        return jsonify({"error": {"code": "WEAK_PASSWORD", "message": str(exc)}}), 422
    u = User(tenant_id=uuid.UUID(str(g.tenant_id)), username=data["username"],
             email=data["email"].strip().lower(),
             password_hash=hash_password(data["password"]), is_active=True,
             created_by=me, updated_by=me)
    db.session.add(u)
    db.session.flush()
    role_ids = list(data.get("role_ids", []))
    if data.get("role_id"):
        role_ids.append(data["role_id"])
    for role_id in role_ids:
        db.session.add(UserRole(tenant_id=u.tenant_id, user_id=u.id,
                                role_id=uuid.UUID(str(role_id)),
                                created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": _dump(u)}), 201


@bp.get("/users/<uuid:user_id>")
@jwt_required()
def get_user(user_id):
    denied = _deny("users.view")
    if denied:
        return denied
    u = db.session.get(User, user_id)
    if u is None or u.is_deleted or str(u.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": _dump(u)})


@bp.put("/users/<uuid:user_id>")
@jwt_required()
def update_user(user_id):
    denied = _deny("users.create")
    if denied:
        return denied
    u = db.session.get(User, user_id)
    if u is None or u.is_deleted or str(u.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))

    def _as_bool(v):
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "active", "نشط")

    if "is_active" in data:
        u.is_active = _as_bool(data["is_active"])
    if data.get("password"):
        from ...utils.security import validate_password as _vp
        try:
            _vp(data["password"])
        except ValueError as exc:
            return jsonify({"error": {"code": "WEAK_PASSWORD", "message": str(exc)}}), 422
        u.password_hash = hash_password(data["password"])
    role_ids = data.get("role_ids")
    if data.get("role_id"):
        role_ids = [data["role_id"]]
    if role_ids is not None:
        db.session.query(UserRole).filter_by(user_id=u.id).delete()
        for role_id in role_ids:
            db.session.add(UserRole(tenant_id=u.tenant_id, user_id=u.id,
                                    role_id=uuid.UUID(str(role_id)),
                                    created_by=me, updated_by=me))
    u.updated_by = me
    db.session.commit()
    return jsonify({"data": _dump(u)})


@bp.post("/users/<uuid:user_id>/deactivate")
@jwt_required()
def deactivate_user(user_id):
    denied = _deny("users.deactivate")
    if denied:
        return denied
    u = db.session.get(User, user_id)
    if u is None or u.is_deleted or str(u.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if u.id == uuid.UUID(str(get_jwt().get("sub"))):
        return jsonify({"error": {"code": "CANNOT_DEACTIVATE_SELF"}}), 409
    u.is_active = False
    db.session.commit()
    from ...services import audit_service as _audit_svc
    _audit_svc.record(tenant_id=u.tenant_id, actor_id=get_jwt().get("sub"),
                      action="deactivate", entity_type="users", entity_id=u.id)
    db.session.commit()
    return jsonify({"data": {"id": str(u.id), "is_active": False}})


@bp.get("/roles")
@jwt_required()
def list_roles():
    denied = _deny("users.view")
    if denied:
        return denied
    rows = db.session.query(Role).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(r.id), "code": r.code, "name_ar": r.name_ar} for r in rows]})
