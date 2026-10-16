"""Seed the 13-actor RBAC matrix (spec section 5). Idempotent."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, Role, Permission, RolePermission  # noqa: E402
from sqlalchemy import text  # noqa: E402

ALL = [p.code for p in []]  # filled below from catalog

MATRIX = {
    # role: permissions (* = all catalog)
    "TENANT_OWNER": ["*", "admin.*"],
    "TENANT_ADMIN": ["*", "admin.*"],
    "FINANCE_MANAGER": ["entities.view", "branches.manage", "journals.post", "journals.reverse",
                        "journals.approve", "journals.create", "accounts.create", "accounts.update",
                        "reports.view", "export.data", "period.close", "sales.manage", "sales.view",
                        "purchases.manage", "purchases.view", "treasury.manage", "treasury.view",
                        "parties.manage", "parties.view", "products.manage", "inventory.manage",
                        "inventory.view",                         "payroll.manage", "education.manage", "projects.manage",
                        "audit.view"],
    "CHIEF_ACCOUNTANT": ["entities.view", "journals.post", "journals.reverse", "journals.approve",
                         "accounts.create", "accounts.update", "reports.view", "period.close",
                         "sales.manage", "purchases.manage", "treasury.manage", "audit.view"],
    "ACCOUNTANT": ["entities.view", "journals.post", "reports.view", "sales.manage",
                   "purchases.manage", "treasury.manage", "parties.manage", "products.manage",
                   "payroll.manage", "education.manage", "projects.manage"],
    "DATA_ENTRY": ["sales.manage", "purchases.manage", "treasury.manage", "entities.view"],
    "CASHIER": ["treasury.manage", "entities.view"],
    "PURCHASING": ["purchases.manage", "purchases.view", "parties.view", "products.manage"],
    "SALES_OFFICER": ["sales.manage", "sales.view", "parties.view", "products.manage"],
    "INVENTORY_KEEPER": ["inventory.manage", "inventory.view", "products.manage"],
    "HR_OFFICER": ["payroll.manage", "entities.view", "reports.view"],
    "INTERNAL_AUDITOR": ["reports.view", "audit.view", "export.data", "entities.view"],
    "EXTERNAL_AUDITOR": ["reports.view", "audit.view"],
}
ROLE_NAMES = {
    "TENANT_OWNER": "مالك المؤسسة", "TENANT_ADMIN": "مدير النظام",
    "FINANCE_MANAGER": "المدير المالي", "CHIEF_ACCOUNTANT": "رئيس الحسابات",
    "ACCOUNTANT": "محاسب", "DATA_ENTRY": "مدخل البيانات", "CASHIER": "أمين الصندوق",
    "PURCHASING": "مسؤول المشتريات", "SALES_OFFICER": "مسؤول المبيعات",
    "INVENTORY_KEEPER": "مسؤول المخزون", "HR_OFFICER": "مسؤول الموارد البشرية",
    "INTERNAL_AUDITOR": "مدقق داخلي", "EXTERNAL_AUDITOR": "مدقق خارجي",
}

def main():
    app = create_app()
    with app.app_context():
        t = db.session.query(Tenant).filter_by(code=os.getenv("TENANT_CODE", "DEMO")).first()
        assert t
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
        admin = db.session.query(User).filter_by(tenant_id=t.id, email="admin@demo.local").first()
        catalog = {p.code: p for p in db.session.query(Permission).all()}
        for code, name in ROLE_NAMES.items():
            role = db.session.query(Role).filter_by(tenant_id=t.id, code=code).first()
            if role is None:
                role = Role(tenant_id=t.id, code=code, name_ar=name,
                            created_by=admin.id, updated_by=admin.id)
                db.session.add(role)
                db.session.flush()
            want = MATRIX[code]
            if "*" in want:
                want = sorted(set(catalog.keys()) | (set(want) - {"*"}))
            have = {rp.permission_id for rp in
                    db.session.query(RolePermission).filter_by(role_id=role.id).all()}
            for perm_code in want:
                perm = catalog.get(perm_code)
                if perm and perm.id not in have:
                    db.session.add(RolePermission(tenant_id=t.id, role_id=role.id,
                                                  permission_id=perm.id,
                                                  created_by=admin.id, updated_by=admin.id))
        db.session.commit()
        print("RBAC_OK roles=", len(ROLE_NAMES))


if __name__ == "__main__":
    main()
