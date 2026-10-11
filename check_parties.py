import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', database='accounting_db')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='parties'")
for row in cur.fetchall():
    print(row[0])
cur.close()
conn.close()