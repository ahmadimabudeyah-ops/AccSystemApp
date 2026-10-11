"""Seed: default accounting policy + party types + type assignments."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.entity import Entity  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.party import Party  # noqa: E402
from sqlalchemy import text  # noqa: E402

POLICY_COLS = ("tenant_id", "entity_id", "code", "framework", "revenue_recognition",
               "expense_recognition", "inventory_method", "capitalization_threshold",
               "depreciation_method", "rounding_method", "rounding_limit",
               "doc_numbering_policy", "effective_from", "status")

app = create_app()
with app.app_context():
    t = db.session.query(Tenant).filter_by(code="DEMO").first()
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    e = db.session.query(Entity).filter_by(tenant_id=t.id, code="MAIN").first()
    admin = db.session.query(User).filter_by(tenant_id=t.id, email="admin@demo.local").first()

    n = db.session.execute(text(
        "SELECT count(*) FROM accounting_policies WHERE tenant_id = :t AND entity_id = :e"),
        {"t": str(t.id), "e": str(e.id)}).scalar()
    if not n:
        db.session.execute(text(
            "INSERT INTO accounting_policies(tenant_id, entity_id, code, framework,"
            " revenue_recognition, expense_recognition, inventory_method,"
            " capitalization_threshold, depreciation_method, rounding_method, rounding_limit,"
            " doc_numbering_policy, effective_from, status, created_by, updated_by)"
            " VALUES (:t, :e, 'IFRS-SME-2026', 'IFRS_SME', 'accrual', 'accrual', 'average',"
            " 500.000, 'straight_line', 'half_up', 0.005, '{\"invoice\": \"INV-{YYYY}-{####}\"}',"
            " '2026-01-01', 'approved', :u, :u)"),
            {"t": str(t.id), "e": str(e.id), "u": str(admin.id)})

    TYPES = [("customer", "عميل"), ("supplier", "مورد"), ("employee", "موظف"),
             ("student", "طالب"), ("guardian", "ولي أمر"), ("bank", "بنك"),
             ("government", "جهة حكومية"), ("partner", "شريك"), ("other", "أخرى")]
    type_ids = {}
    for code, ar in TYPES:
        row = db.session.execute(text(
            "SELECT id FROM party_types WHERE tenant_id = :t AND code = :c"),
            {"t": str(t.id), "c": code}).first()
        if row is None:
            row = db.session.execute(text(
                "INSERT INTO party_types(tenant_id, code, name_ar, created_by, updated_by)"
                " VALUES (:t, :c, :a, :u, :u) RETURNING id"),
                {"t": str(t.id), "c": code, "a": ar, "u": str(admin.id)}).first()
        type_ids[code] = row[0]
    ASSIGN = {"C-001": "customer", "S-001": "supplier", "G-001": "guardian",
              "ST-001": "student"}
    for pcode, tcode in ASSIGN.items():
        p = db.session.query(Party).filter_by(tenant_id=t.id, entity_id=e.id, code=pcode).first()
        if p is None:
            continue
        exists = db.session.execute(text(
            "SELECT 1 FROM party_type_assignments WHERE tenant_id = :t AND party_id = :p"
            " AND party_type_id = :y"), {"t": str(t.id), "p": str(p.id), "y": str(type_ids[tcode])}).first()
        if not exists:
            db.session.execute(text(
                "INSERT INTO party_type_assignments(tenant_id, party_id, party_type_id,"
                " is_primary, created_by, updated_by)"
                " VALUES (:t, :p, :y, TRUE, :u, :u)"),
                {"t": str(t.id), "p": str(p.id), "y": str(type_ids[tcode]), "u": str(admin.id)})
    db.session.commit()
    print("SEED3_OK")
