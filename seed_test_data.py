#!/usr/bin/env python
"""Comprehensive seed data for end-to-end testing."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, r'C:\AccSystem\backend')
os.environ.setdefault('DATABASE_URL', 'postgresql://accounting:accounting123@127.0.0.1:5433/accounting_db')

from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.entity import Entity
from app.models.account import Account
from app.models.journal import Journal
from app.models.party import Party, PartyAddress, PartyContact
from app.models.product import Product, ProductCategory, UoM as UOM, Warehouse, Location
from app.models.sales import PaymentTerm
from app.models.asset import AssetCategory
from app.models.treasury import CashBox, Bank, BankAccount
from app.services.auth_service import AuthError
from sqlalchemy import text as _text

app = create_app()

def get_demo_tenant():
    with app.app_context():
        return db.session.query(Tenant).filter_by(code='DEMO').first()

def seed_all():
    with app.app_context():
        tenant = get_demo_tenant()
        if not tenant:
            print("[ERROR] DEMO tenant not found")
            return
        print(f"[OK] Tenant: {tenant.name_ar} ({tenant.id})")
        
        # Set RLS context for this tenant
        from sqlalchemy import text as _text
        db.session.execute(_text('SET LOCAL app.current_tenant_id = :t'), {"t": str(tenant.id)})
        
        entity = db.session.query(Entity).filter_by(tenant_id=tenant.id).first()
        if not entity:
            print("[ERROR] No entity found")
            return
        print(f"[OK] Entity: {entity.name_ar} ({entity.id})")
        
        # 1. Payment Terms
        terms_data = [
            ("IMMEDIATE", "فوري", 0),
            ("NET15", "15 يوم", 15),
            ("NET30", "30 يوم", 30),
            ("NET60", "60 يوم", 60),
            ("NET90", "90 يوم", 90),
        ]
        for code, name, days in terms_data:
            t = db.session.query(PaymentTerm).filter_by(tenant_id=tenant.id, entity_id=entity.id, code=code).first()
            if not t:
                t = PaymentTerm(tenant_id=tenant.id, entity_id=entity.id, code=code, name_ar=name, days=days)
                db.session.add(t)
        db.session.commit()
        print("[OK] Payment terms")
        
        # 2. UOMs
        uoms = [
            ("PCS", "قطعة", 1.0),
            ("KG", "كيلوجرام", 1.0),
            ("M", "متر", 1.0),
            ("M2", "متر مربع", 1.0),
            ("L", "لتر", 1.0),
            ("BOX", "صندوق", 1.0),
        ]
        for code, name, factor in uoms:
            u = db.session.query(UOM).filter_by(tenant_id=tenant.id, code=code).first()
            if not u:
                u = UOM(tenant_id=tenant.id, code=code, name_ar=name, factor=factor)
                db.session.add(u)
        db.session.commit()
        print("[OK] UOMs")
        
        # 3. Product Categories
        cat = db.session.query(ProductCategory).filter_by(tenant_id=tenant.id, code='GOODS').first()
        if not cat:
            cat = ProductCategory(tenant_id=tenant.id, code='GOODS', name_ar='بضاعة', is_active=True)
            db.session.add(cat)
        cat_svc = db.session.query(ProductCategory).filter_by(tenant_id=tenant.id, code='SERVICE').first()
        if not cat_svc:
            cat_svc = ProductCategory(tenant_id=tenant.id, code='SERVICE', name_ar='خدمة', is_active=True)
            db.session.add(cat_svc)
        db.session.commit()
        print("[OK] Product categories")
        
        # 4. Party Types - use raw SQL
        db.session.execute(_text("""
            INSERT INTO party_types (tenant_id, code, name_ar, name_en)
            VALUES 
            (:t, 'customer', 'عميل', 'Customer'),
            (:t, 'supplier', 'مورد', 'Supplier'),
            (:t, 'employee', 'موظف', 'Employee'),
            (:t, 'student', 'طالب', 'Student'),
            (:t, 'guardian', 'ولي أمر', 'Guardian'),
            (:t, 'bank', 'بنك', 'Bank'),
            (:t, 'government', 'جهة حكومية', 'Government'),
            (:t, 'other', 'أخرى', 'Other')
            ON CONFLICT (tenant_id, code) DO NOTHING
        """), {"t": tenant.id})
        db.session.commit()
        print("[OK] Party types")
        
        # 5. Customers
        customers_data = [
            ("شركة النور للتجارة", "CUST-001", "0791234567", "عمان، الأردن"),
            ("مؤسسة الأندلس", "CUST-002", "0792345678", "إربد، الأردن"),
            ("شركة البركة", "CUST-003", "0793456789", "الزرقاء، الأردن"),
            ("متجر الأمل", "CUST-004", "0794567890", "عمان، الأردن"),
            ("شركة المستقبل", "CUST-005", "0795678901", "الكرك، الأردن"),
        ]
        for name, code, phone, addr in customers_data:
            p = db.session.query(Party).filter_by(tenant_id=tenant.id, code=code).first()
            if not p:
                p = Party(
                    tenant_id=tenant.id, entity_id=entity.id,
                    code=code, name_ar=name, phone=phone, address=addr,
                    credit_limit=50000, currency_id='JOD', status='active',
                    legal_type='company', default_currency='JOD'
                )
                db.session.add(p)
                db.session.flush()
                # Assign customer type
                db.session.execute(_text("""
                    INSERT INTO party_type_assignments (tenant_id, party_id, party_type_id)
                    SELECT :t, :p, id FROM party_types WHERE tenant_id = :t AND code = 'customer'
                    ON CONFLICT (tenant_id, party_id, party_type_id) DO NOTHING
                """), {"t": tenant.id, "p": p.id})
        db.session.commit()
        print("[OK] Customers")
        
        # 6. Suppliers
        suppliers_data = [
            ("شركة الإمداد المركزية", "SUPP-001", "0781112233", "عمان، الأردن"),
            ("مؤسسة الخليج", "SUPP-002", "0782223344", "دبي، الإمارات"),
            ("شركة التوريد السريع", "SUPP-003", "0783334455", "عمان، الأردن"),
        ]
        for name, code, phone, addr in suppliers_data:
            p = db.session.query(Party).filter_by(tenant_id=tenant.id, code=code).first()
            if not p:
                p = Party(
                    tenant_id=tenant.id, entity_id=entity.id,
                    code=code, name_ar=name, phone=phone, address=addr,
                    currency_id='JOD', status='active',
                    legal_type='company', default_currency='JOD'
                )
                db.session.add(p)
                db.session.flush()
                db.session.execute(_text("""
                    INSERT INTO party_type_assignments (tenant_id, party_id, party_type_id)
                    SELECT :t, :p, id FROM party_types WHERE tenant_id = :t AND code = 'supplier'
                    ON CONFLICT (tenant_id, party_id, party_type_id) DO NOTHING
                """), {"t": tenant.id, "p": p.id})
        db.session.commit()
        print("[OK] Suppliers")
        
        # 7. Products
        uom_pcs = db.session.query(UOM).filter_by(tenant_id=tenant.id, code='PCS').first()
        uom_kg = db.session.query(UOM).filter_by(tenant_id=tenant.id, code='KG').first()
        products_data = [
            ("منتج أ", "PRD-001", cat.id, uom_pcs.id, 10.0, 25.0, 5.0),
            ("منتج ب", "PRD-002", cat.id, uom_pcs.id, 15.0, 35.0, 16.0),
            ("منتج ج", "PRD-003", cat.id, uom_kg.id, 8.0, 20.0, 10.0),
            ("منتج د", "PRD-004", cat.id, uom_pcs.id, 12.0, 30.0, 0.0),
            ("منتج ه", "PRD-005", cat.id, uom_pcs.id, 20.0, 50.0, 16.0),
            ("خدمة صيانة", "SRV-001", cat_svc.id, uom_pcs.id, 0.0, 100.0, 16.0),
            ("استشارة تقنية", "SRV-002", cat_svc.id, uom_pcs.id, 0.0, 200.0, 0.0),
        ]
        for name, code, cat_id, uom_id, cost, price, tax_pct in products_data:
            p = db.session.query(Product).filter_by(tenant_id=tenant.id, code=code).first()
            if not p:
                p = Product(
                    tenant_id=tenant.id, entity_id=entity.id, category_id=cat_id,
                    uom_id=uom_id, code=code, name_ar=name,
                    avg_cost=cost, sale_price=price, tax_rate_pct=tax_pct,
                    is_active=True, track_stock=(cat_id == cat.id)
                )
                db.session.add(p)
        db.session.commit()
        print("[OK] Products")
        
        # 8. Warehouses & Locations
        wh = db.session.query(Warehouse).filter_by(tenant_id=tenant.id, code='WH-MAIN').first()
        if not wh:
            wh = Warehouse(tenant_id=tenant.id, entity_id=entity.id, code='WH-MAIN', name_ar='المستودع الرئيسي', is_active=True)
            db.session.add(wh)
            db.session.commit()
        loc_a = db.session.query(Location).filter_by(warehouse_id=wh.id, code='A-01').first()
        if not loc_a:
            loc_a = Location(warehouse_id=wh.id, code='A-01', name_ar='رف أ-01', is_active=True)
            db.session.add(loc_a)
        loc_b = db.session.query(Location).filter_by(warehouse_id=wh.id, code='B-01').first()
        if not loc_b:
            loc_b = Location(warehouse_id=wh.id, code='B-01', name_ar='رف ب-01', is_active=True)
            db.session.add(loc_b)
        db.session.commit()
        print("[OK] Warehouses & Locations")
        
        # 9. Asset Categories
        ast_cat = db.session.query(AssetCategory).filter_by(tenant_id=tenant.id, code='EQUIP').first()
        if not ast_cat:
            ast_cat = AssetCategory(tenant_id=tenant.id, code='EQUIP', name_ar='معدات', depreciation_rate=20.0)
            db.session.add(ast_cat)
        ast_cat2 = db.session.query(AssetCategory).filter_by(tenant_id=tenant.id, code='VEHICLE').first()
        if not ast_cat2:
            ast_cat2 = AssetCategory(tenant_id=tenant.id, code='VEHICLE', name_ar='مركبات', depreciation_rate=15.0)
            db.session.add(ast_cat2)
        db.session.commit()
        print("[OK] Asset categories")
        
        # 10. Journals
        journals_data = [
            ("SALES", "مبيعات", "sale"),
            ("PURCH", "مشتريات", "purchase"),
            ("CASH", "نقدية", "cash"),
            ("BANK", "بنكية", "bank"),
            ("GEN", "عامة", "general"),
        ]
        default_acc = db.session.query(Account).filter_by(tenant_id=tenant.id, entity_id=entity.id, is_postable=True).first()
        for code, name, jtype in journals_data:
            j = db.session.query(Journal).filter_by(tenant_id=tenant.id, code=code).first()
            if not j:
                j = Journal(
                    tenant_id=tenant.id, entity_id=entity.id, code=code, name=name, type=jtype,
                    currency_id='JOD', default_account_id=default_acc.id if default_acc else None,
                    sequence_prefix=code, sequence_length=6, requires_approval=True, allow_manual=True
                )
                db.session.add(j)
        db.session.commit()
        print("[OK] Journals")
        
        # 11. Cash Boxes
        cb = db.session.query(CashBox).filter_by(tenant_id=tenant.id, code='CB-MAIN').first()
        if not cb:
            cb = CashBox(tenant_id=tenant.id, entity_id=entity.id, code='CB-MAIN', name_ar='الصندوق الرئيسي', opening_balance=10000, currency_id='JOD', status='active')
            db.session.add(cb)
        db.session.commit()
        print("[OK] Cash boxes")
        
        # 12. Banks & Bank Accounts
        bank = db.session.query(Bank).filter_by(tenant_id=tenant.id, code='BANK-01').first()
        if not bank:
            bank = Bank(tenant_id=tenant.id, code='BANK-01', name_ar='البنك الأهلي', swift='AHLIJOAX', currency_id='JOD')
            db.session.add(bank)
            db.session.commit()
        ba = db.session.query(BankAccount).filter_by(tenant_id=tenant.id, account_no='1234567890').first()
        if not ba:
            ba = BankAccount(tenant_id=tenant.id, entity_id=entity.id, bank_id=bank.id, account_no='1234567890', iban='JO94AHLI1234567890123456789012', currency_id='JOD', is_active=True)
            db.session.add(ba)
        db.session.commit()
        print("[OK] Banks & accounts")
        
        print("\n[SUCCESS] All seed data created successfully!")
        print(f"Tenant ID: {tenant.id}")
        print(f"Entity ID: {entity.id}")

if __name__ == '__main__':
    seed_all()