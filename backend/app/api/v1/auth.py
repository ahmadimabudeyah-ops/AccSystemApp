"""Auth endpoints: login + refresh + me."""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ...extensions import limiter
from ...services.auth_service import authenticate, AuthError

bp = Blueprint("auth", __name__)


@bp.post("/login")
@limiter.limit(lambda: current_app.config.get("LOGIN_RATELIMIT", "10 per minute"))
def login():
    data = request.get_json(force=True) or {}
    tenant_id = request.headers.get("X-Tenant-ID") or data.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": {"code": "TENANT_REQUIRED"}}), 400
    try:
        return jsonify(authenticate(tenant_id, data.get("username", ""), data.get("password", "")))
    except AuthError as exc:
        return jsonify({"error": {"code": "AUTH_FAILED", "message": str(exc)}}), 401


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    from flask_jwt_extended import create_access_token
    from ...services.auth_service import get_user_permissions
    claims = get_jwt()
    tenant_id = claims.get("tenant_id")
    try:
        permissions = get_user_permissions(get_jwt_identity(), tenant_id)
    except Exception:
        permissions = claims.get("permissions", [])
    token = create_access_token(identity=get_jwt_identity(),
                                additional_claims={"tenant_id": tenant_id,
                                                   "permissions": permissions})
    return jsonify({"access_token": token, "permissions": permissions})


@bp.get("/me")
@jwt_required()
def me():
    claims = get_jwt()
    return jsonify({"user_id": get_jwt_identity(), "tenant_id": claims.get("tenant_id"),
                    "permissions": claims.get("permissions", [])})


@bp.post("/forgot-password")
def forgot_password():
    from ...services import ops_service
    data = request.get_json(force=True) or {}
    result = ops_service.request_password_reset(
        tenant_id=data.get("tenant_id"), username=data.get("username", ""))
    return jsonify({"data": result})


@bp.post("/reset-password")
def reset_password():
    from ...services import ops_service
    from ...services.errors import ValidationError
    data = request.get_json(force=True) or {}
    try:
        result = ops_service.reset_password(token=data.get("token", ""),
                                            new_password=data.get("new_password", ""))
    except ValidationError as exc:
        return jsonify({"error": {"code": "WEAK_OR_EXPIRED", "message": str(exc)}}), 400
    return jsonify({"data": result})
