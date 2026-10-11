import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', database='accounting_db')
cur = conn.cursor()
cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'product_categories'::regclass")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()