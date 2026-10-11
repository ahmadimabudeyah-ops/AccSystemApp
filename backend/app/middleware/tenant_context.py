"""Tenant context middleware — sets PostgreSQL RLS variable per request.

Contract: API requests (/api/*, except login/refresh/health) must carry
X-Tenant-ID. Web pages (browser navigation) are exempt — they render shells
and fetch data via the API with JWT from session storage.

Implementation: SET (session-level) so the context survives COMMITs inside
the request (SET LOCAL would vanish after the first commit and break lazy
refreshes with RLS). teardown_appcontext RESETs it so pooled connections
never leak one tenant's context into the next request (fail-closed).
"""
from flask import request, g, jsonify
from sqlalchemy import text
from ..extensions import db

OPEN_PATHS = {"/health", "/api/v1/auth/login", "/api/v1/auth/refresh",
              "/api/v1/auth/forgot-password", "/api/v1/tenants/provision",
              "/api/v1/plans", "/api/v1/openapi.json"}
GUC = "app.current_tenant_id"


def tenant_context():
    if request.path in OPEN_PATHS or not request.path.startswith("/api/"):
        g.tenant_id = request.headers.get("X-Tenant-ID")
        return None
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return jsonify({"error": {"code": "TENANT_REQUIRED", "message": "X-Tenant-ID header is required"}}), 400
    g.tenant_id = tenant_id
    # Cross-check: a JWT minted for tenant A must never access tenant B,
    # even if the caller forges X-Tenant-ID (defense in depth over RLS).
    # Header accepts UUID *or* tenant code (e.g. DEMO).
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from flask_jwt_extended import decode_token
            from ..models.tenant import Tenant
            claims = decode_token(auth[7:])
            jwt_tenant = (claims or {}).get("tenant_id")
            if jwt_tenant:
                try:
                    import uuid as _uuid
                    header_uuid = str(_uuid.UUID(str(tenant_id)))
                except (ValueError, AttributeError):
                    t = db.session.query(Tenant).filter_by(
                        code=str(tenant_id).strip(), is_deleted=False).first()
                    header_uuid = str(t.id) if t else None
                if header_uuid is None or str(jwt_tenant) != header_uuid:
                    return jsonify({"error": {"code": "TENANT_MISMATCH"}}), 403
                g.tenant_id = header_uuid
        except Exception:
            pass  # invalid/expired token -> the endpoint's @jwt_required answers 401
    db.session.execute(text(f"SET {GUC} = :t"), {"t": g.tenant_id})
    return None


def reset_tenant_context(_exc=None):
    try:
        db.session.execute(text(f"RESET {GUC}"))
    except Exception:
        pass


def init_app(app):
    app.teardown_appcontext(reset_tenant_context)
