import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', database='accounting_db')
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '%product%'")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()