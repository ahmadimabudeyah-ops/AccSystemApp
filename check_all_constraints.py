import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', database='accounting_db')
cur = conn.cursor()
tables = ['uoms', 'payment_terms', 'product_categories', 'warehouses', 'locations', 
          'asset_categories', 'journals', 'cash_boxes', 'banks', 'bank_accounts',
          'accounts', 'parties', 'products', 'party_types', 'party_type_assignments']
for t in tables:
    try:
        cur.execute(f"SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = '{t}'::regclass AND contype = 'u'")
        rows = cur.fetchall()
        if rows:
            print(f"\n=== {t} ===")
            for row in rows:
                print(f"  {row[0]}: {row[1]}")
    except Exception as e:
        print(f"{t}: {e}")
cur.close()
conn.close()