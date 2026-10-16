"""One-command delivery bootstrap + verification.

Usage (from backend/):
    python scripts/deliver.py            # seed if needed, then verify everything
    python scripts/deliver.py --fresh     # wipe transactions and rebuild the demo story

Starts nothing by itself: run `python wsgi.py` (or scripts/run_server.py <port>)
in a second terminal first, or pass --port <p> to match.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, ".."))
PY = sys.executable

STEPS = [
    ("seed_base", [PY, "scripts/seed_base.py"]),
    ("seed_rbac", [PY, "scripts/seed_rbac.py"]),
]


def main() -> int:
    fresh = "--fresh" in sys.argv
    port = "5000"
    if "--port" in sys.argv:
        port = sys.argv[sys.argv.index("--port") + 1]
    os.environ["BASE_PORT"] = port
    env = dict(os.environ)

    def run(label, argv, cwd=BACKEND):
        print(f"\n=== {label} ===", flush=True)
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                           timeout=1800)
        out = (p.stdout + p.stderr).strip()
        print("\n".join(out.splitlines()[-4:]), flush=True)
        print(f"--- {label}: {'OK' if p.returncode == 0 else 'FAIL'}", flush=True)
        return p.returncode == 0

    if fresh:
        run("reseed (wipe transactions)", [PY, "scripts/reseed_demo.py"])
        run("seed_demo_full", [PY, "scripts/seed_demo_full.py"])
    else:
        for label, argv in STEPS:
            if not run(label, argv):
                return 1
        # demo data only when the dataset is empty
        chk = subprocess.run([PY, "-c", "import sys;sys.path.insert(0,'.');"
                              "from sqlalchemy import text;from app import create_app;"
                              "from app.extensions import db;a=create_app();"
                              "c=a.app_context();c.push();"
                              "t=db.session.execute(text(\"select id from tenants "
                              "where code='DEMO'\")).scalar();"
                              "db.session.execute(text('SET app.current_tenant_id=:x'),"
                              "{'x':str(t)});"
                              "n=db.session.execute(text(\"select count(*) from "
                              "customer_invoices\")).scalar();print(n)"],
                             cwd=BACKEND, capture_output=True, text=True, env=env)
        empty = (chk.stdout.strip().splitlines() or ["0"])[-1] == "0"
        if empty:
            run("seed_demo_full", [PY, "scripts/seed_demo_full.py"])

    return run("verify_all", [PY, "scripts/verify_all.py", "--port", port])


if __name__ == "__main__":
    sys.exit(main())
