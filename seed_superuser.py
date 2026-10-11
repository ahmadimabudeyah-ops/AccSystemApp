#!/usr/bin/env python
"""Comprehensive seed data via superuser (bypasses RLS)."""
import psycopg2
import uuid
from datetime import date, timedelta

conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', database='accounting_db')
conn.autocommit = True
cur = conn.cursor()

# Get DEMO tenant
cur.execute("SELECT id FROM tenants WHERE code='DEMO'")
tenant_row = cur.fetchone()
TENANT_ID = tenant_row[0]
print(f"Tenant: {TENANT_ID}")

# Get MAIN entity
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM entities WHERE tenant_id = %s AND code = 'MAIN'", (TENANT_ID,))
entity_row = cur.fetchone()
ENTITY_ID = entity_row[0]
print(f"Entity: {ENTITY_ID}")

def exec_safe(sql, params=None):
    cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
    cur.execute(sql, params)

# 1. Payment Terms
terms = [
    ('IMMEDIATE', 'فوري', 0, 'net'),
    ('NET15', '15 يوم', 15, 'net'),
    ('NET30', '30 يوم', 30, 'net'),
    ('NET60', '60 يوم', 60, 'net'),
    ('NET90', '90 يوم', 90, 'net'),
]
for code, name, days, ttype in terms:
    exec_safe("""
        INSERT INTO payment_terms (tenant_id, entity_id, code, name_ar, term_type, days, is_default, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, FALSE, TRUE)
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
    """, (TENANT_ID, ENTITY_ID, code, name, ttype, days))
print("[OK] Payment terms")

# 2. UOMs
uoms = [
    ('PCS', 'قطعة', 1.0),
    ('KG', 'كيلوجرام', 1.0),
    ('M', 'متر', 1.0),
    ('M2', 'متر مربع', 1.0),
    ('L', 'لتر', 1.0),
    ('BOX', 'صندوق', 1.0),
]
for code, name, factor in uoms:
    exec_safe("""
        INSERT INTO uoms (tenant_id, code, name_ar, factor, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (tenant_id, code) DO NOTHING
    """, (TENANT_ID, code, name, factor))
print("[OK] UOMs")

# 3. Product Categories
cats = [
    ('GOODS', 'بضاعة'),
    ('SERVICE', 'خدمة'),
]
for code, name in cats:
    exec_safe("""
        INSERT INTO product_categories (tenant_id, entity_id, code, name_ar, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
    """, (TENANT_ID, ENTITY_ID, code, name))
print("[OK] Product categories")

# Get category IDs
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM product_categories WHERE tenant_id = %s AND code = 'GOODS'", (TENANT_ID,))
cat_goods = cur.fetchone()[0]
cur.execute("SELECT id FROM product_categories WHERE tenant_id = %s AND code = 'SERVICE'", (TENANT_ID,))
cat_svc = cur.fetchone()[0]

# 4. Party Types & Assignments (already done by seed_rbac)

# 5. Customers
customers = [
    ('شركة النور للتجارة', 'CUST-001'),
    ('مؤسسة الأندلس', 'CUST-002'),
    ('شركة البركة', 'CUST-003'),
    ('متجر الأمل', 'CUST-004'),
    ('شركة المستقبل', 'CUST-005'),
]
for name, code in customers:
    exec_safe("""
        INSERT INTO parties (tenant_id, entity_id, code, name_ar, legal_name,
            credit_limit, default_currency, payment_terms_days, credit_currency, status, legal_type)
        VALUES (%s, %s, %s, %s, %s, 50000, 'JOD', 30, 'JOD', 'active', 'company')
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
        RETURNING id
    """, (TENANT_ID, ENTITY_ID, code, name, name))
    pid = cur.fetchone()
    if pid:
        exec_safe("""
            INSERT INTO party_type_assignments (tenant_id, party_id, party_type_id)
            SELECT %s, %s, id FROM party_types WHERE tenant_id = %s AND code = 'customer'
            ON CONFLICT (tenant_id, party_id, party_type_id) DO NOTHING
        """, (TENANT_ID, pid[0], TENANT_ID))
print("[OK] Customers")

# 6. Suppliers
suppliers = [
    ('شركة الإمداد المركزية', 'SUPP-001'),
    ('مؤسسة الخليج', 'SUPP-002'),
    ('شركة التوريد السريع', 'SUPP-003'),
]
for name, code in suppliers:
    exec_safe("""
        INSERT INTO parties (tenant_id, entity_id, code, name_ar, legal_name,
            credit_limit, default_currency, payment_terms_days, credit_currency, status, legal_type)
        VALUES (%s, %s, %s, %s, %s, 50000, 'JOD', 30, 'JOD', 'active', 'company')
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
        RETURNING id
    """, (TENANT_ID, ENTITY_ID, code, name, name))
    pid = cur.fetchone()
    if pid:
        exec_safe("""
            INSERT INTO party_type_assignments (tenant_id, party_id, party_type_id)
            SELECT %s, %s, id FROM party_types WHERE tenant_id = %s AND code = 'supplier'
            ON CONFLICT (tenant_id, party_id, party_type_id) DO NOTHING
        """, (TENANT_ID, pid[0], TENANT_ID))
print("[OK] Suppliers")

# Get some party IDs
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM parties WHERE tenant_id = %s AND code = 'CUST-001'", (TENANT_ID,))
cust1 = cur.fetchone()[0]
cur.execute("SELECT id FROM parties WHERE tenant_id = %s AND code = 'SUPP-001'", (TENANT_ID,))
supp1 = cur.fetchone()[0]

# 7. Products
uom_pcs = cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),)) or cur.execute("SELECT id FROM uoms WHERE tenant_id = %s AND code = 'PCS'", (TENANT_ID,))
cur.execute("SELECT id FROM uoms WHERE tenant_id = %s AND code = 'PCS'", (TENANT_ID,))
uom_pcs = cur.fetchone()[0]
cur.execute("SELECT id FROM uoms WHERE tenant_id = %s AND code = 'KG'", (TENANT_ID,))
uom_kg = cur.fetchone()[0]

products = [
    ('منتج أ', 'PRD-001', cat_goods, uom_pcs, 10.0, 25.0, 5.0, True),
    ('منتج ب', 'PRD-002', cat_goods, uom_pcs, 15.0, 35.0, 16.0, True),
    ('منتج ج', 'PRD-003', cat_goods, uom_kg, 8.0, 20.0, 10.0, True),
    ('منتج د', 'PRD-004', cat_goods, uom_pcs, 12.0, 30.0, 0.0, True),
    ('منتج ه', 'PRD-005', cat_goods, uom_pcs, 20.0, 50.0, 16.0, True),
    ('خدمة صيانة', 'SRV-001', cat_svc, uom_pcs, 0.0, 100.0, 16.0, False),
    ('استشارة تقنية', 'SRV-002', cat_svc, uom_pcs, 0.0, 200.0, 0.0, False),
]
for name, code, cat_id, uom_id, cost, price, tax_pct, track in products:
    exec_safe("""
        INSERT INTO products (tenant_id, entity_id, category_id, base_uom_id, purchase_uom_id, sale_uom_id, code, name_ar,
            avg_cost, sale_price, standard_cost, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
    """, (TENANT_ID, ENTITY_ID, cat_id, uom_id, uom_id, uom_id, name, code, cost, price, cost))
print("[OK] Products")

# Get product IDs
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM products WHERE tenant_id = %s AND code = 'PRD-001'", (TENANT_ID,))
prod1 = cur.fetchone()[0]

# 8. Warehouses & Locations
exec_safe("""
    INSERT INTO warehouses (tenant_id, entity_id, code, name_ar, is_active)
    VALUES (%s, %s, 'WH-MAIN', 'المستودع الرئيسي', TRUE)
    ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
    RETURNING id
""", (TENANT_ID, ENTITY_ID))
wh = cur.fetchone()
if not wh:
    exec_safe("SELECT id FROM warehouses WHERE tenant_id = %s AND entity_id = %s AND code = 'WH-MAIN'", (TENANT_ID, ENTITY_ID))
    wh = cur.fetchone()
wh_id = wh[0]

exec_safe("""
    INSERT INTO locations (tenant_id, warehouse_id, code, name_ar, is_active)
    VALUES (%s, %s, 'A-01', 'رف أ-01', TRUE)
    ON CONFLICT (tenant_id, warehouse_id, code) DO NOTHING
""", (TENANT_ID, wh_id))
exec_safe("""
    INSERT INTO locations (tenant_id, warehouse_id, code, name_ar, is_active)
    VALUES (%s, %s, 'B-01', 'رف ب-01', TRUE)
    ON CONFLICT (tenant_id, warehouse_id, code) DO NOTHING
""", (TENANT_ID, wh_id))
print("[OK] Warehouses & Locations")

# 9. Asset Categories
exec_safe("""
    INSERT INTO asset_categories (tenant_id, code, name_ar, useful_life_years, depreciation_method)
    VALUES (%s, 'EQUIP', 'معدات', 5, 'straight_line')
    ON CONFLICT (tenant_id, code) DO NOTHING
""", (TENANT_ID,))
exec_safe("""
    INSERT INTO asset_categories (tenant_id, code, name_ar, useful_life_years, depreciation_method)
    VALUES (%s, 'VEHICLE', 'مركبات', 7, 'straight_line')
    ON CONFLICT (tenant_id, code) DO NOTHING
""", (TENANT_ID,))
print("[OK] Asset categories")

# 10. Journals
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM accounts WHERE tenant_id = %s AND entity_id = %s AND is_postable = TRUE LIMIT 1", (TENANT_ID, ENTITY_ID))
default_acc = cur.fetchone()
default_acc_id = default_acc[0] if default_acc else None

journals = [
    ('SALES', 'مبيعات', 'sale'),
    ('PURCH', 'مشتريات', 'purchase'),
    ('CASH', 'نقدية', 'cash'),
    ('BANK', 'بنكية', 'bank'),
    ('GEN', 'عامة', 'general'),
]
for code, name, jtype in journals:
    exec_safe("""
        INSERT INTO journals (tenant_id, entity_id, code, name_ar, journal_type, default_currency,
            default_account_id, prefix, number_length, require_approval, allow_manual)
        VALUES (%s, %s, %s, %s, %s, 'JOD', %s, %s, 6, TRUE, TRUE)
        ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
    """, (TENANT_ID, ENTITY_ID, code, name, jtype, default_acc_id, code))
print("[OK] Journals")

# 11. Cash Boxes
cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
cur.execute("SELECT id FROM branches WHERE tenant_id = %s AND entity_id = %s LIMIT 1", (TENANT_ID, ENTITY_ID))
branch = cur.fetchone()
branch_id = branch[0] if branch else ENTITY_ID

exec_safe("""
    INSERT INTO cash_boxes (tenant_id, entity_id, branch_id, code, name_ar, opening_balance, currency_id, is_active)
    VALUES (%s, %s, %s, 'CB-MAIN', 'الصندوق الرئيسي', 10000, 'JOD', TRUE)
    ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
""", (TENANT_ID, ENTITY_ID, branch_id))
print("[OK] Cash boxes")

# 12. Banks & Bank Accounts
exec_safe("""
    INSERT INTO banks (tenant_id, code, name_ar, swift_code, is_active)
    VALUES (%s, 'BANK-01', 'البنك الأهلي', 'AHLIJOAX', TRUE)
    ON CONFLICT (tenant_id, code) DO NOTHING
    RETURNING id
""", (TENANT_ID,))
bank = cur.fetchone()
if not bank:
    cur.execute("SET LOCAL app.current_tenant_id = %s", (str(TENANT_ID),))
    cur.execute("SELECT id FROM banks WHERE tenant_id = %s AND code = 'BANK-01'", (TENANT_ID,))
    bank = cur.fetchone()
bank_id = bank[0]

exec_safe("""
    INSERT INTO bank_accounts (tenant_id, entity_id, bank_id, code, iban, currency_id, is_active)
    VALUES (%s, %s, %s, 'BANK-01-ACC', 'JO94AHLI1234567890123456789012', 'JOD', TRUE)
    ON CONFLICT (tenant_id, entity_id, code) DO NOTHING
""", (TENANT_ID, ENTITY_ID, bank_id))
print("[OK] Banks & accounts")

print("\n[SUCCESS] All seed data created successfully!")
print(f"Tenant ID: {TENANT_ID}")
print(f"Entity ID: {ENTITY_ID}")

cur.close()
conn.close()