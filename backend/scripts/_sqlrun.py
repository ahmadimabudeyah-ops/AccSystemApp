"""Execute a SQL file as the database owner (bypasses immutability triggers).

Used by maintenance/repair scripts that must delete already-posted documents.
Credentials come from DATABASE_URL in backend/.env; the owner role is resolved
from PostgreSQL and its password is read from the PGPASSWORD-style fallback
env var PGPASSWORD_OWNER (defaults to 'postgres').

Usage:  python scripts/_sqlrun.py path\to\file.sql
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.parse


def owner_and_url() -> tuple[str, str, str, str, str]:
    url = os.getenv("DATABASE_URL")
    if not url:
        with open(os.path.join(os.path.dirname(__file__), "..", ".env"),
                  encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    if not url:
        raise SystemExit("DATABASE_URL not found")
    url = url.replace("postgresql://", "postgresql://")
    p = urllib.parse.urlparse(url)
    host = p.hostname or "127.0.0.1"
    port = str(p.port or 5433)
    database = (p.path or "/accounting_db").lstrip("/")
    return url, host, port, database, p.username or "accounting"


def run_python(url: str, sql_path: str) -> int:
    """Fallback for hosts without psql (e.g. Render Shell)."""
    import psycopg2

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    with open(sql_path, encoding="utf-8") as fh:
        sql = fh.read()
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()
    print("OK (python driver)")
    return 0


def main() -> int:
    sql_path = sys.argv[1]
    url, host, port, database, user = owner_and_url()
    psql = shutil.which("psql")
    if not psql:
        for cand in (r"C:\Program Files\PostgreSQL\18\bin\psql.exe",
                     r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
                     r"C:\Program Files\PostgreSQL\16\bin\psql.exe"):
            if os.path.exists(cand):
                psql = cand
                break
    if not psql or os.getenv("SQLRUN_FORCE_PYTHON") == "1":
        return run_python(url, sql_path)

    # ask the DB which role owns the public schema, then run as that role
    q = subprocess.run([psql, "-U", user, "-h", host, "-p", port, "-d", database,
                        "-t", "-A", "-c",
                        "SELECT tableowner FROM pg_tables WHERE schemaname='public'"
                        " LIMIT 1"],
                       capture_output=True, text=True,
                       env=dict(os.environ, PGPASSWORD=os.getenv("PGPASSWORD", "")))
    owner = (q.stdout.strip() or user)
    pw = os.getenv("PGPASSWORD_OWNER", os.getenv("PGPASSWORD", ""))
    r = subprocess.run([psql, "-U", owner, "-h", host, "-p", port, "-d", database,
                        "-v", "ON_ERROR_STOP=1", "-f", sql_path],
                       capture_output=True, text=True,
                       env=dict(os.environ, PGPASSWORD=pw))
    sys.stdout.write(r.stdout[-2000:])
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
