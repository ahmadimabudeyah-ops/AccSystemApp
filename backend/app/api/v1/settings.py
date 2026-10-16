"""Settings API: general/company tenant settings + own profile + roles + integrations.

GET/PUT  /api/v1/settings/general   (currency, timezone)
GET/PUT  /api/v1/settings/company    (name_ar, tax_id)
GET/PUT  /api/v1/users/me            (full_name, email)
POST     /api/v1/roles               (code, name_ar)
"""
from __future__ import annotations
import os
import uuid
import hashlib
import secrets
from datetime import date
from flask import Blueprint, request, jsonify, g, send_file
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


# ------------------------------------------------------------- integrations & webhooks

@bp.get("/integrations")
@jwt_required()
def list_integrations():
    from ...models.addons import Integration
    rows = db.session.query(Integration).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Integration.code).limit(50).all()
    return jsonify({"data": [{"id": str(i.id), "code": i.code, "kind": i.kind,
                              "is_active": i.is_active} for i in rows]})


@bp.post("/integrations")
@jwt_required()
def create_integration():
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import Integration
    data = request.get_json(force=True)
    i = Integration(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], kind=data.get("kind", "webhook"),
        config=data.get("config", {}), is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(i)
    db.session.commit()
    return jsonify({"data": {"id": str(i.id), "code": i.code}}), 201


@bp.get("/webhooks")
@jwt_required()
def list_webhooks():
    from ...models.addons import Webhook, Integration
    int_ids = [r.id for r in db.session.query(Integration).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()]
    rows = []
    if int_ids:
        from sqlalchemy import or_
        rows = db.session.query(Webhook).filter(
            Webhook.integration_id.in_(int_ids), Webhook.is_deleted == False
        ).order_by(Webhook.event).limit(50).all()
    return jsonify({"data": [{"id": str(w.id), "integration_id": str(w.integration_id),
                              "event": w.event, "target_url": w.target_url,
                              "is_active": w.is_active} for w in rows]})


@bp.post("/webhooks")
@jwt_required()
def create_webhook():
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import Webhook
    data = request.get_json(force=True)
    w = Webhook(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        integration_id=uuid.UUID(str(data["integration_id"])),
        event=data["event"], target_url=data["target_url"],
        secret=data.get("secret"), is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(w)
    db.session.commit()
    return jsonify({"data": {"id": str(w.id)}}), 201


# ------------------------------------------------------------- attachments

@bp.get("/attachments")
@jwt_required()
def list_attachments():
    from ...models.addons import Attachment
    q = db.session.query(Attachment).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("linked_type"):
        q = q.filter_by(linked_type=request.args["linked_type"])
    if request.args.get("linked_id"):
        q = q.filter_by(linked_id=uuid.UUID(request.args["linked_id"]))
    rows = q.order_by(Attachment.created_at.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(a.id), "file_name": a.file_name,
                              "file_type": a.file_type, "file_size": a.file_size,
                              "linked_type": a.linked_type,
                              "linked_id": str(a.linked_id) if a.linked_id else None}
                             for a in rows]})


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "instance", "uploads")


@bp.post("/attachments")
@jwt_required()
def upload_attachment():
    from ...models.addons import Attachment
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "file required"}}), 422
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    blob = f.read()
    if len(blob) > 20 * 1024 * 1024:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "max 20MB"}}), 422
    file_hash = hashlib.sha256(blob).hexdigest()
    rel_dir = os.path.join(str(tenant_id), file_hash[:2])
    abs_dir = os.path.join(UPLOAD_DIR, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    safe_name = os.path.basename(f.filename)
    abs_path = os.path.join(abs_dir, f"{file_hash}_{safe_name}")
    if not os.path.exists(abs_path):
        with open(abs_path, "wb") as fh:
            fh.write(blob)
    a = Attachment(
        tenant_id=tenant_id,
        entity_id=uuid.UUID(str(request.form["entity_id"])) if request.form.get("entity_id") else None,
        file_name=safe_name,
        file_type=f.mimetype, file_size=len(blob),
        storage_path=os.path.join(rel_dir, f"{file_hash}_{safe_name}"),
        file_hash=file_hash,
        linked_type=request.form.get("linked_type"),
        linked_id=uuid.UUID(request.form["linked_id"]) if request.form.get("linked_id") else None,
        created_by=me, updated_by=me)
    db.session.add(a)
    db.session.commit()
    return jsonify({"data": {"id": str(a.id), "file_name": a.file_name,
                             "file_size": a.file_size}}), 201


@bp.get("/attachments/<uuid:att_id>/download")
@jwt_required()
def download_attachment(att_id):
    from ...models.addons import Attachment
    a = db.session.get(Attachment, att_id)
    if a is None or a.is_deleted or str(a.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    abs_path = os.path.normpath(os.path.join(UPLOAD_DIR, a.storage_path))
    if not abs_path.startswith(os.path.normpath(UPLOAD_DIR)) or not os.path.isfile(abs_path):
        return jsonify({"error": {"code": "NOT_FOUND",
                                  "message": "file missing on disk"}}), 404
    return send_file(abs_path, as_attachment=True, download_name=a.file_name)


# ------------------------------------------------------------- document templates

@bp.get("/document-templates")
@jwt_required()
def list_templates():
    from ...models.addons import DocumentTemplate
    rows = db.session.query(DocumentTemplate).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(DocumentTemplate.code).limit(50).all()
    return jsonify({"data": [{"id": str(t.id), "code": t.code,
                              "name_ar": t.name_ar, "kind": t.kind,
                              "is_active": t.is_active} for t in rows]})


@bp.post("/document-templates")
@jwt_required()
def create_template():
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import DocumentTemplate
    data = request.get_json(force=True)
    t = DocumentTemplate(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"],
        kind=data.get("kind", "invoice"), body=data.get("body", ""),
        is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(t)
    db.session.commit()
    return jsonify({"data": {"id": str(t.id), "code": t.code}}), 201


@bp.put("/document-templates/<uuid:tpl_id>")
@jwt_required()
def update_template(tpl_id):
    denied = _deny("admin.*")
    if denied:
        return denied
    from ...models.addons import DocumentTemplate
    t = db.session.get(DocumentTemplate, tpl_id)
    if t is None or t.is_deleted or str(t.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    if "body" in data:
        t.body = data["body"]
    if "name_ar" in data:
        t.name_ar = data["name_ar"]
    if "is_active" in data:
        t.is_active = bool(data["is_active"])
    t.updated_by = uuid.UUID(str(get_jwt().get("sub")))
    db.session.commit()
    return jsonify({"data": {"id": str(t.id), "code": t.code}})


# ------------------------------------------------------------- delegations & api keys

@bp.get("/delegations")
@jwt_required()
def list_delegations():
    from ...models.addons import Delegation
    me = uuid.UUID(str(get_jwt().get("sub")))
    rows = db.session.query(Delegation).filter(
        Delegation.from_user_id == me, Delegation.is_deleted == False
    ).order_by(Delegation.starts_on.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(d.id), "to_user_id": str(d.to_user_id),
                              "starts_on": d.starts_on.isoformat(),
                              "ends_on": d.ends_on.isoformat(),
                              "scope": d.scope, "is_active": d.is_active}
                             for d in rows]})


@bp.post("/delegations")
@jwt_required()
def create_delegation():
    from ...models.addons import Delegation
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    d = Delegation(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        from_user_id=me, to_user_id=uuid.UUID(str(data["to_user_id"])),
        starts_on=date.fromisoformat(data["starts_on"]),
        ends_on=date.fromisoformat(data["ends_on"]),
        scope=data.get("scope", "all"), is_active=True,
        created_by=me, updated_by=me)
    db.session.add(d)
    db.session.commit()
    return jsonify({"data": {"id": str(d.id)}}), 201


@bp.get("/api-keys")
@jwt_required()
def list_api_keys():
    from ...models.addons import ApiKey
    me = uuid.UUID(str(get_jwt().get("sub")))
    rows = db.session.query(ApiKey).filter_by(
        user_id=me, is_deleted=False
    ).order_by(ApiKey.created_at.desc()).limit(50).all()
    return jsonify({"data": [{"id": str(k.id), "prefix": k.prefix,
                              "scopes": k.scopes,
                              "expires_on": k.expires_on.isoformat() if k.expires_on else None,
                              "is_active": k.is_active} for k in rows]})


@bp.post("/api-keys")
@jwt_required()
def create_api_key():
    import hashlib
    import secrets
    from ...models.addons import ApiKey
    data = request.get_json(force=True, silent=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    raw = secrets.token_urlsafe(32)
    key = ApiKey(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        user_id=me, prefix=raw[:8],
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        scopes=data.get("scopes", []),
        expires_on=date.fromisoformat(data["expires_on"]) if data.get("expires_on") else None,
        is_active=True,
        created_by=me, updated_by=me)
    db.session.add(key)
    db.session.commit()
    return jsonify({"data": {"id": str(key.id), "key": raw,
                             "warning": "key shown only once"}}), 201
