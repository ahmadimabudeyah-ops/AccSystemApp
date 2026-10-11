"""Seed currencies + Jordan taxes + engine permissions for treasury/assets APIs."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.entity import Entity  # noqa: E402
from app.models.user import User, Role, RolePermission, Permission  # noqa: E402
from app.models.treasury import Currency, Tax, Bank, BankAccount, CashBox  # noqa: E402
from app.models.asset import AssetCategory  # noqa: E402
from sqlalchemy import text  # noqa: E402

CURRENCIES = [("JOD", "دينار أردني", "Jordanian Dinar", 3),
              ("USD", "دولار أمريكي", "US Dollar", 2),
              ("EUR", "يورو", "Euro", 2),
              ("SAR", "ريال سعودي", "Saudi Riyal", 2),
              ("AED", "درهم إماراتي", "UAE Dirham", 2)]
PERMS = ["treasury.manage"]

app = create_app()
with app.app_context():
    t = db.session.query(Tenant).filter_by(code=os.getenv("TENANT_CODE", "DEMO")).first()
    assert t
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    admin = db.session.query(User).filter_by(tenant_id=t.id, email="admin@demo.local").first()
    for code, ar, en, dec in CURRENCIES:
        if not db.session.query(Currency).filter_by(tenant_id=t.id, code=code).first():
            db.session.add(Currency(tenant_id=t.id, code=code, name_ar=ar, name_en=en,
                                    decimals=dec, created_by=admin.id, updated_by=admin.id))
    for p in PERMS:
        if not db.session.query(Permission).filter_by(code=p).first():
            db.session.add(Permission(code=p, name_ar="إدارة الخزينة والأصول",
                                      module="treasury"))
    db.session.flush()
    for role_code in ("TENANT_ADMIN", "ACCOUNTANT", "CASHIER"):
        role = db.session.query(Role).filter_by(tenant_id=t.id, code=role_code).first()
        if role is None:
            continue
        for p in PERMS:
            perm = db.session.query(Permission).filter_by(code=p).first()
            if not db.session.query(RolePermission).filter_by(role_id=role.id, permission_id=perm.id).first():
                db.session.add(RolePermission(tenant_id=t.id, role_id=role.id,
                                              permission_id=perm.id,
                                              created_by=admin.id, updated_by=admin.id))
    for e in db.session.query(Entity).filter_by(tenant_id=t.id).all():
        if not db.session.query(Tax).filter_by(tenant_id=t.id, entity_id=e.id, code="VAT16").first():            db.session.add(Tax(tenant_id=t.id, entity_id=e.id, code="VAT16",
                               name_ar="ضريبة المبيعات 16%", rate=16,
                               created_by=admin.id, updated_by=admin.id))
        if not db.session.query(CashBox).filter_by(tenant_id=t.id, entity_id=e.id, code="MAIN").first():
            db.session.add(CashBox(tenant_id=t.id, entity_id=e.id, code="MAIN",
                                   name_ar="الصندوق الرئيسي", created_by=admin.id, updated_by=admin.id))
        if not db.session.query(AssetCategory).filter_by(tenant_id=t.id, code="EQUIP").first():
            db.session.add(AssetCategory(tenant_id=t.id, code="EQUIP",
                                         name_ar="آلات ومعدات", useful_life_years=5,
                                         created_by=admin.id, updated_by=admin.id))
        if not db.session.query(Bank).filter_by(tenant_id=t.id, code="AHLI").first():
            bank = Bank(tenant_id=t.id, code="AHLI", name_ar="البنك الأهلي",
                        created_by=admin.id, updated_by=admin.id)
            db.session.add(bank)
            db.session.flush()
        else:
            bank = db.session.query(Bank).filter_by(tenant_id=t.id, code="AHLI").first()
        if not db.session.query(BankAccount).filter_by(
                tenant_id=t.id, entity_id=e.id, code="AHLI-JOD").first():
            db.session.add(BankAccount(
                tenant_id=t.id, entity_id=e.id, bank_id=bank.id, code="AHLI-JOD",
                iban="JO94CBJO0010000000000131000302", currency_id="JOD",
                created_by=admin.id, updated_by=admin.id))
    db.session.commit()
    print("SEED8_OK")
