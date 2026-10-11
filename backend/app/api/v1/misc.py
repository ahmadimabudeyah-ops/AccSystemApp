"""Notifications API + OpenAPI spec endpoint."""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.ops import Notification

bp = Blueprint("misc", __name__)


@bp.get("/notifications")
@jwt_required()
def list_notifications():
    q = db.session.query(Notification).filter_by(
        tenant_id=uuid.UUID(str(g_tenant())), is_deleted=False)
    if request.args.get("unread") == "1":
        q = q.filter_by(is_read=False)
    rows = q.order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(n.id), "title": n.title, "body": n.body,
                              "severity": n.severity, "is_read": n.is_read,
                              "link_url": n.link_url} for n in rows]})


def g_tenant():
    from flask import g
    return g.tenant_id


@bp.post("/notifications")
@jwt_required()
def create_notification():
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    n = Notification(tenant_id=uuid.UUID(str(g_tenant())), user_id=me,
                     title=data["title"], body=data.get("body"),
                     severity=data.get("severity", "info"),
                     link_url=data.get("link_url"), created_by=me, updated_by=me)
    db.session.add(n)
    db.session.commit()
    return jsonify({"data": {"id": str(n.id)}}), 201


@bp.post("/notifications/<uuid:nid>/read")
@jwt_required()
def read_notification(nid):
    n = db.session.get(Notification, nid)
    if n is None or n.is_deleted or str(n.tenant_id) != str(g_tenant()):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    n.is_read = True
    db.session.commit()
    return jsonify({"data": {"id": str(n.id), "is_read": True}})


@bp.get("/openapi.json")
def openapi():
    """مواصفة حية مولدة من خريطة المسارات المسجلة فعلًا."""
    paths = {}
    for rule in current_app.url_map.iter_rules():
        if not str(rule).startswith("/api/"):
            continue
        methods = sorted((rule.methods or set()) - {"HEAD", "OPTIONS"})
        paths.setdefault(str(rule), {})["methods"] = methods
        paths[str(rule)]["endpoint"] = rule.endpoint
    return jsonify({"openapi": "3.0.0", "title": "Accounting Platform API",
                    "version": "v1", "paths": paths,
                    "security": "Bearer JWT + X-Tenant-ID"})
