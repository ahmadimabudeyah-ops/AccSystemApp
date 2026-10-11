"""Products + UoM + warehouses/locations API."""
from __future__ import annotations
import uuid
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.product import Product, ProductCategory, UoM, Warehouse, Location

bp = Blueprint("products", __name__)
PAGE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


@bp.get("/uoms")
@jwt_required()
def list_uoms():
    rows = db.session.query(UoM).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(u.id), "code": u.code, "name_ar": u.name_ar} for u in rows]})


@bp.post("/uoms")
@jwt_required()
def create_uom():
    denied = _deny("products.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    u = UoM(tenant_id=uuid.UUID(str(g.tenant_id)), code=data["code"],
            name_ar=data["name_ar"], factor=data.get("factor", 1), created_by=me, updated_by=me)
    db.session.add(u)
    db.session.commit()
    return jsonify({"data": {"id": str(u.id)}}), 201


@bp.get("/product-categories")
@jwt_required()
def list_categories():
    rows = db.session.query(ProductCategory).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(c.id), "entity_id": str(c.entity_id), "code": c.code,
                              "name_ar": c.name_ar} for c in rows]})


@bp.post("/product-categories")
@jwt_required()
def create_category():
    denied = _deny("products.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    c = ProductCategory(tenant_id=uuid.UUID(str(g.tenant_id)),
                        entity_id=uuid.UUID(str(data["entity_id"])),
                        code=data["code"], name_ar=data["name_ar"], created_by=me, updated_by=me)
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


def _dump(p: Product) -> dict:
    return {"id": str(p.id), "entity_id": str(p.entity_id), "code": p.code,
            "name_ar": p.name_ar, "product_type": p.product_type,
            "sale_price": float(p.sale_price), "avg_cost": float(p.avg_cost),
            "status": p.status}


@bp.get("/products")
@jwt_required()
def list_products():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(Product).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((Product.code.like(like)) | (Product.name_ar.like(like)))
    rows = q.order_by(Product.code).offset((page - 1) * PAGE).limit(PAGE).all()
    return jsonify({"data": [_dump(p) for p in rows], "page": page})


@bp.post("/products")
@jwt_required()
def create_product():
    denied = _deny("products.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    p = Product(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                code=data["code"], name_ar=data["name_ar"],
                product_type=data.get("product_type", "stockable"),
                category_id=uuid.UUID(str(data["category_id"])) if data.get("category_id") else None,
                base_uom_id=uuid.UUID(str(data["base_uom_id"])) if data.get("base_uom_id") else None,
                cost_method=data.get("cost_method", "average"),
                standard_cost=data.get("standard_cost", 0), sale_price=data.get("sale_price", 0),
                status="active", created_by=me, updated_by=me)
    db.session.add(p)
    db.session.commit()
    return jsonify({"data": _dump(p)}), 201


@bp.get("/products/<uuid:product_id>")
@jwt_required()
def get_product(product_id):
    p = db.session.get(Product, product_id)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": _dump(p)})


@bp.put("/products/<uuid:product_id>")
@jwt_required()
def update_product(product_id):
    denied = _deny("products.manage")
    if denied:
        return denied
    p = db.session.get(Product, product_id)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    for field in ("name_ar", "name_en", "sale_price", "standard_cost", "status"):
        if field in data:
            setattr(p, field, data[field])
    p.updated_by = uuid.UUID(str(get_jwt().get("sub")))
    db.session.commit()
    return jsonify({"data": _dump(p)})


@bp.get("/warehouses")
@jwt_required()
def list_warehouses():
    rows = db.session.query(Warehouse).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(w.id), "entity_id": str(w.entity_id), "code": w.code,
                              "name_ar": w.name_ar} for w in rows]})


@bp.post("/warehouses")
@jwt_required()
def create_warehouse():
    denied = _deny("products.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    w = Warehouse(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                  code=data["code"], name_ar=data["name_ar"], created_by=me, updated_by=me)
    db.session.add(w)
    db.session.flush()
    loc = Location(tenant_id=w.tenant_id, warehouse_id=w.id, code="STOCK",
                   name_ar="مخزن رئيسي", location_type="internal", created_by=me, updated_by=me)
    db.session.add(loc)
    db.session.commit()
    return jsonify({"data": {"id": str(w.id), "default_location_id": str(loc.id)}}), 201


@bp.get("/warehouses/<uuid:wh_id>/locations")
@jwt_required()
def warehouse_locations(wh_id):
    rows = db.session.query(Location).filter_by(warehouse_id=wh_id, is_deleted=False).all()
    return jsonify({"data": [{"id": str(l.id), "code": l.code, "name_ar": l.name_ar,
                              "location_type": l.location_type} for l in rows]})
