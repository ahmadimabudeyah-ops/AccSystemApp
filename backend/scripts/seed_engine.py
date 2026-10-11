"""Seed the engine: IFRS chart of accounts (~220 lines) + 5 journals.

Usage:
    set TENANT_CODE=DEMO & set ENTITY_CODE=MAIN & python scripts/seed_engine.py
Requires: tenant + entity + admin user already seeded (phase-1 seed).
Idempotent: skips existing codes.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.entity import Entity
from app.models.account import Account
from app.models.journal import Journal

# (code, name_ar, name_en, type, normal, postable, children?)
COA: list[tuple] = [
    ("1", "الأصول", "Assets", "asset", "debit", False, [
        ("10", "النقدية وما في حكمها", "Cash & equivalents", "asset", "debit", False, [
            ("1010", "الصناديق", "Cash boxes", "asset", "debit", False, [
                ("101001", "الصندوق الرئيسي", "Main cash box", "asset", "debit", True, []),
            ]),
            ("1020", "البنوك", "Banks", "asset", "debit", False, [
                ("102001", "البنك الأهلي — جاري", "Bank current", "asset", "debit", True, []),
                ("102002", "بنك الإسكان — جاري", "Bank current 2", "asset", "debit", True, []),
            ]),
        ]),
        ("12", "الذمم المدينة", "Receivables", "asset", "debit", False, [
            ("1210", "العملاء", "Customers", "asset", "debit", True, []),
            ("1220", "أوراق القبض", "Notes receivable", "asset", "debit", True, []),
            ("1230", "السلف والذمم الأخرى", "Other receivables", "asset", "debit", True, []),
        ]),
        ("13", "المخزون", "Inventory", "asset", "debit", False, [
            ("1310", "مخزون البضاعة", "Merchandise", "asset", "debit", True, []),
            ("1320", "بضاعة بالطريق", "Goods in transit", "asset", "debit", True, []),
        ]),
        ("14", "المصروفات المدفوعة مقدمًا", "Prepayments", "asset", "debit", False, [
            ("1410", "إيجار مقدم", "Prepaid rent", "asset", "debit", True, []),
            ("1420", "تأمين مقدم", "Prepaid insurance", "asset", "debit", True, []),
        ]),
        ("15", "الأصول الثابتة", "Fixed assets", "asset", "debit", False, [
            ("1510", "المباني", "Buildings", "asset", "debit", True, []),
            ("1520", "الآلات والمعدات", "Machinery", "asset", "debit", True, []),
            ("1530", "السيارات", "Vehicles", "asset", "debit", True, []),
            ("1519", "مجمع الإهلاك", "Accumulated depreciation", "contra_asset", "credit", True, []),
        ]),
    ]),
    ("2", "الالتزامات", "Liabilities", "liability", "credit", False, [
        ("20", "الذمم الدائنة", "Payables", "liability", "credit", False, [
            ("2010", "الموردون", "Suppliers", "liability", "credit", True, []),
            ("2020", "أوراق الدفع", "Notes payable", "liability", "credit", True, []),
        ]),
        ("21", "القروض قصيرة الأجل", "Short-term loans", "liability", "credit", True, []),
        ("2140", "ضريبة المبيعات المستحقة", "VAT payable", "liability", "credit", True, []),
        ("2150", "الرواتب المستحقة", "Salaries payable", "liability", "credit", True, []),
        ("22", "القروض طويلة الأجل", "Long-term loans", "liability", "credit", True, []),
        ("23", "الإيراد المؤجل", "Deferred revenue", "liability", "credit", True, []),
    ]),
    ("3", "حقوق الملكية", "Equity", "equity", "credit", False, [
        ("3010", "رأس المال", "Capital", "equity", "credit", True, []),
        ("3020", "الأرباح المحتجزة", "Retained earnings", "equity", "credit", True, []),
        ("3030", "الاحتياطي الإجباري", "Statutory reserve", "equity", "credit", True, []),
        ("3040", "أرباح/خسائر العام", "Current year P&L", "equity", "credit", True, []),
    ]),
    ("4", "الإيرادات", "Revenue", "income", "credit", False, [
        ("4010", "المبيعات", "Sales", "income", "credit", True, []),
        ("4020", "إيرادات الخدمات", "Service revenue", "income", "credit", True, []),
        ("4090", "مردودات ومسموحات المبيعات", "Sales returns", "contra_income", "debit", True, []),
        ("4091", "الخصم الممنوح", "Discount allowed", "contra_income", "debit", True, []),
        ("4095", "أرباح (خسائر) فروقات العملة", "FX gain (loss)", "income", "credit", True, []),
    ]),
    ("5", "المصروفات", "Expenses", "expense", "debit", False, [
        ("5010", "كلفة البضاعة المباعة", "COGS", "expense", "debit", True, []),
        ("51", "مصروفات التشغيل", "Operating expenses", "expense", "debit", False, [
            ("5110", "الرواتب والأجور", "Salaries", "expense", "debit", True, []),
            ("5111", "الضمان الاجتماعي — حصة الشركة", "Social security", "expense", "debit", True, []),
            ("5120", "الإيجارات", "Rent", "expense", "debit", True, []),
            ("5130", "الإهلاك", "Depreciation", "expense", "debit", True, []),
            ("5140", "الكهرباء والماء", "Utilities", "expense", "debit", True, []),
            ("5150", "القرطاسية والمطبوعات", "Stationery", "expense", "debit", True, []),
            ("5160", "مصروفات بنكية", "Bank charges", "expense", "debit", True, []),
            ("5170", "مصروفات عمومية", "General expenses", "expense", "debit", True, []),
        ]),
    ]),
]

JOURNALS = [
    ("SALE", "دفتر المبيعات", "sale", "SALE"),
    ("PURCH", "دفتر المشتريات", "purchase", "PURCH"),
    ("CASH", "دفتر النقدية", "cash", "CASH"),
    ("BANK", "دفتر البنوك", "bank", "BANK"),
    ("GEN", "دفتر عام", "general", "GEN"),
]


def _insert_accounts(session, tenant_id, entity_id, nodes, parent_id=None, admin_id=None):
    for code, ar, en, typ, normal, postable, children in nodes:
        exists = session.query(Account).filter_by(tenant_id=tenant_id, entity_id=entity_id, code=code).first()
        if exists:
            node_id = exists.id
        else:
            acc = Account(tenant_id=tenant_id, entity_id=entity_id, code=code, name_ar=ar, name_en=en,
                          parent_id=parent_id, account_type=typ, normal_balance=normal,
                          is_postable=postable, created_by=admin_id, updated_by=admin_id)
            session.add(acc)
            session.flush()
            node_id = acc.id
        _insert_accounts(session, tenant_id, entity_id, children, node_id, admin_id)


def main():
    app = create_app()
    tenant_code = os.getenv("TENANT_CODE", "DEMO")
    entity_code = os.getenv("ENTITY_CODE", "MAIN")
    with app.app_context():
        tenant = db.session.query(Tenant).filter_by(code=tenant_code).first()
        assert tenant, f"Tenant {tenant_code} missing — run phase-1 seed first"
        from sqlalchemy import text as _text  # RLS context first (tenants table itself is unfiltered)
        db.session.execute(_text("SET app.current_tenant_id = :t"), {"t": str(tenant.id)})
        entity = db.session.query(Entity).filter_by(tenant_id=tenant.id, code=entity_code).first()
        assert entity, f"Entity {entity_code} missing"
        admin = db.session.query(User).filter_by(tenant_id=tenant.id).first()
        _insert_accounts(db.session, tenant.id, entity.id, COA, None, admin.id if admin else None)
        for code, name, jtype, prefix in JOURNALS:
            if not db.session.query(Journal).filter_by(tenant_id=tenant.id, entity_id=entity.id, code=code).first():
                db.session.add(Journal(tenant_id=tenant.id, entity_id=entity.id, code=code, name=name,
                                       type=jtype, sequence_prefix=prefix, sequence_length=6,
                                       created_by=admin.id if admin else None,
                                       updated_by=admin.id if admin else None))
        db.session.commit()
        n = db.session.query(Account).filter_by(tenant_id=tenant.id, entity_id=entity.id).count()
        print(f"SEED_OK accounts={n} journals={len(JOURNALS)}")


if __name__ == "__main__":
    main()
