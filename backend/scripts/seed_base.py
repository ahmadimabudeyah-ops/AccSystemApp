"""Bootstrap seed: DEMO tenant + admin + MAIN entity/branch + FY2026 + roles.

Usage:  python scripts/seed_base.py
Idempotent: skips whatever already exists. Then chains seed_engine.py.
Login: tenant DEMO / admin@demo.local / Admin@123
"""
from __future__ import annotations
import calendar
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, Role, Permission, RolePermission, UserRole  # noqa: E402
from app.models.entity import Entity, Branch, FiscalYear, FiscalPeriod  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

TENANT_CODE = os.getenv("TENANT_CODE", "DEMO")
ENTITY_CODE = os.getenv("ENTITY_CODE", "MAIN")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@demo.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")

ROLES = [
    ("TENANT_ADMIN", "مدير المؤسسة"),
    ("ACCOUNTANT", "محاسب"),
    ("AUDITOR", "مدقق"),
    ("CASHIER", "أمين صندوق"),
    ("HR_OFFICER", "موظف موارد بشرية"),
]


def main() -> None:
    app = create_app()
    with app.app_context():
        tenant = db.session.query(Tenant).filter_by(code=TENANT_CODE).first()
        if tenant is None:
            tenant = Tenant(code=TENANT_CODE, name_ar="مؤسسة تجريبية", name_en="Demo Tenant")
            db.session.add(tenant)
            db.session.flush()
        from sqlalchemy import text as _text  # RLS context for all subsequent writes
        db.session.execute(_text("SET app.current_tenant_id = :t"), {"t": str(tenant.id)})
        admin = db.session.query(User).filter_by(tenant_id=tenant.id, email=ADMIN_EMAIL).first()
        if admin is None:
            admin = User(tenant_id=tenant.id, username="admin", email=ADMIN_EMAIL,
                         password_hash=hash_password(ADMIN_PASSWORD, rounds=4))
            db.session.add(admin)
            db.session.flush()
            admin.created_by = admin.id
            admin.updated_by = admin.id
        for code, ar in ROLES:
            role = db.session.query(Role).filter_by(tenant_id=tenant.id, code=code).first()
            if role is None:
                role = Role(tenant_id=tenant.id, code=code, name_ar=ar,
                            created_by=admin.id, updated_by=admin.id)
                db.session.add(role)
                db.session.flush()
            if not db.session.query(UserRole).filter_by(user_id=admin.id, role_id=role.id).first():
                db.session.add(UserRole(tenant_id=tenant.id, user_id=admin.id, role_id=role.id,
                                        created_by=admin.id, updated_by=admin.id))
        # TENANT_ADMIN gets every permission in the catalog
        ta = db.session.query(Role).filter_by(tenant_id=tenant.id, code="TENANT_ADMIN").first()
        for perm in db.session.query(Permission).all():
            if not db.session.query(RolePermission).filter_by(role_id=ta.id, permission_id=perm.id).first():
                db.session.add(RolePermission(tenant_id=tenant.id, role_id=ta.id,
                                              permission_id=perm.id,
                                              created_by=admin.id, updated_by=admin.id))
        entity = db.session.query(Entity).filter_by(tenant_id=tenant.id, code=ENTITY_CODE).first()
        if entity is None:
            entity = Entity(tenant_id=tenant.id, code=ENTITY_CODE, name_ar="الكيان الرئيسي",
                            functional_currency="JOD", created_by=admin.id, updated_by=admin.id)
            db.session.add(entity)
            db.session.flush()
        if not db.session.query(Branch).filter_by(tenant_id=tenant.id, entity_id=entity.id, code="HQ").first():
            db.session.add(Branch(tenant_id=tenant.id, entity_id=entity.id, code="HQ",
                                  name_ar="الفرع الرئيسي", created_by=admin.id, updated_by=admin.id))
        year = db.session.query(FiscalYear).filter_by(tenant_id=tenant.id, entity_id=entity.id, code="2026").first()
        if year is None:
            year = FiscalYear(tenant_id=tenant.id, entity_id=entity.id, code="2026",
                              name_ar="السنة المالية 2026", starts_on=date(2026, 1, 1),
                              ends_on=date(2026, 12, 31), status="open",
                              created_by=admin.id, updated_by=admin.id)
            db.session.add(year)
            db.session.flush()
        for m in range(1, 13):
            code = f"2026-{m:02d}"
            if db.session.query(FiscalPeriod).filter_by(tenant_id=tenant.id, entity_id=entity.id, code=code).first():
                continue
            last = calendar.monthrange(2026, m)[1]
            db.session.add(FiscalPeriod(
                tenant_id=tenant.id, entity_id=entity.id, fiscal_year_id=year.id, code=code,
                period_number=m, name_ar=f"فترة {code}", starts_on=date(2026, m, 1),
                ends_on=date(2026, m, last), status="open",
                created_by=admin.id, updated_by=admin.id))
        db.session.commit()
        print(f"BASE_OK tenant={tenant.id} entity={entity.id} admin={admin.id}")


if __name__ == "__main__":
    main()
    import subprocess  # noqa: E402
    env = dict(os.environ, TENANT_CODE=TENANT_CODE, ENTITY_CODE=ENTITY_CODE)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "seed_engine.py")],
                   env=env, check=True)
