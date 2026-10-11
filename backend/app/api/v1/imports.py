"""CSV bulk import: parties + products (idempotent by code)."""
from __future__ import annotations
import csv
import io
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.party import Party
from ...models.product import Product

bp = Blueprint("imports", __name__)


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


@bp.post("/import/parties")
@jwt_required()
def import_parties():
    denied = _deny("parties.manage")
    if denied:
        return denied
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    text = request.files["file"].read().decode("utf-8-sig")
    created, skipped = 0, 0
    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("code") or "").strip()
        if not code:
            continue
        exists = db.session.query(Party).filter_by(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(row["entity_id"])),
            code=code).first()
        if exists:
            skipped += 1
            continue
        db.session.add(Party(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(row["entity_id"])),
            code=code, name_ar=row.get("name_ar", code),
            status="active", credit_limit=row.get("credit_limit") or 0,
            created_by=me, updated_by=me))
        created += 1
    db.session.commit()
    return jsonify({"data": {"created": created, "skipped": skipped}}), 201


@bp.post("/import/products")
@jwt_required()
def import_products():
    denied = _deny("products.manage")
    if denied:
        return denied
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    text = request.files["file"].read().decode("utf-8-sig")
    created, skipped = 0, 0
    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("code") or "").strip()
        if not code:
            continue
        exists = db.session.query(Product).filter_by(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(row["entity_id"])),
            code=code).first()
        if exists:
            skipped += 1
            continue
        db.session.add(Product(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(row["entity_id"])),
            code=code, name_ar=row.get("name_ar", code),
            product_type=row.get("product_type", "stockable"),
            sale_price=row.get("sale_price") or 0,
            standard_cost=row.get("standard_cost") or 0,
            status="active", created_by=me, updated_by=me))
        created += 1
    db.session.commit()
    return jsonify({"data": {"created": created, "skipped": skipped}}), 201
