import psycopg2

conn = psycopg2.connect(host='127.0.0.1', port=5433, user='accounting', password='accounting123', database='accounting_db')
conn.autocommit = True
cur = conn.cursor()

# Get DEMO tenant ID
cur.execute('SELECT id FROM tenants WHERE code=%s', ('DEMO',))
tenant = cur.fetchone()
print('Tenant:', tenant)

if tenant:
    tid = tenant[0]
    # Insert entity with RLS context
    cur.execute('SET LOCAL app.current_tenant_id = %s', (str(tid),))
    cur.execute("""
        INSERT INTO entities (tenant_id, code, name_ar, functional_currency)
        VALUES (%s, 'MAIN', 'الكيان الرئيسي', 'JOD')
        ON CONFLICT (tenant_id, code) DO NOTHING
        RETURNING id
    """, (tid,))
    result = cur.fetchone()
    print('Entity created:', result)

cur.close()
conn.close()