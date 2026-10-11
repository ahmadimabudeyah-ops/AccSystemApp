"""Seed demo parties/products/uoms/terms for sales-purchases cycle."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.entity import Entity  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.party import Party  # noqa: E402
from app.models.product import Product, ProductCategory, UoM  # noqa: E402
from app.models.sales import PaymentTerm  # noqa: E402
from app.models.product import Warehouse, Location  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    t = db.session.query(Tenant).filter_by(code="DEMO").first()
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    e = db.session.query(Entity).filter_by(tenant_id=t.id, code="MAIN").first()
    admin = db.session.query(User).filter_by(tenant_id=t.id, email="admin@demo.local").first()

    def get_or_new(model, filt, **kw):
        row = db.session.query(model).filter_by(**filt).first()
        if row is None:
            row = model(**kw)
            db.session.add(row)
            db.session.flush()
        return row

    uom = get_or_new(UoM, {"tenant_id": t.id, "code": "PCS"},
                     tenant_id=t.id, code="PCS", name_ar="قطعة",
                     created_by=admin.id, updated_by=admin.id)
    cat = get_or_new(ProductCategory, {"tenant_id": t.id, "entity_id": e.id, "code": "GEN"},
                     tenant_id=t.id, entity_id=e.id, code="GEN", name_ar="عام",
                     created_by=admin.id, updated_by=admin.id)
    get_or_new(Product, {"tenant_id": t.id, "entity_id": e.id, "code": "P-001"},
               tenant_id=t.id, entity_id=e.id, code="P-001", name_ar="صنف تجريبي 1",
               category_id=cat.id, base_uom_id=uom.id, sale_price=100,
               standard_cost=60, status="active",
               created_by=admin.id, updated_by=admin.id)
    get_or_new(Party, {"tenant_id": t.id, "entity_id": e.id, "code": "C-001"},
               tenant_id=t.id, entity_id=e.id, code="C-001", name_ar="عميل تجريبي",
               status="active", created_by=admin.id, updated_by=admin.id)
    get_or_new(Party, {"tenant_id": t.id, "entity_id": e.id, "code": "S-001"},
               tenant_id=t.id, entity_id=e.id, code="S-001", name_ar="مورد تجريبي",
               status="active", created_by=admin.id, updated_by=admin.id)
    get_or_new(PaymentTerm, {"tenant_id": t.id, "entity_id": e.id, "code": "NET30"},
               tenant_id=t.id, entity_id=e.id, code="NET30", name_ar="30 يوم",
               days=30, is_default=True, created_by=admin.id, updated_by=admin.id)
    wh = get_or_new(Warehouse, {"tenant_id": t.id, "entity_id": e.id, "code": "WH1"},
                    tenant_id=t.id, entity_id=e.id, code="WH1", name_ar="المستودع الرئيسي",
                    created_by=admin.id, updated_by=admin.id)
    locs = db.session.query(Location).filter_by(warehouse_id=wh.id, is_deleted=False).all()
    if not locs:
        db.session.add(Location(tenant_id=t.id, warehouse_id=wh.id, code="STOCK",
                                name_ar="مخزن رئيسي", location_type="internal",
                                created_by=admin.id, updated_by=admin.id))
        db.session.flush()
    db.session.commit()
    print("SEED_DEMO_OK")
