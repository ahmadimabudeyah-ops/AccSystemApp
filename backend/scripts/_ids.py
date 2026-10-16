"""Resolve tenant/entity ids for verification scripts.

Usage:
    from _ids import TID, EID  (or) from scripts._ids import ...
Reads DEMO tenant + MAIN entity from the configured database so that the
verification suite survives a rebuild/reseed of the schema.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

TENANT_CODE = os.getenv("TENANT_CODE", "DEMO")
ENTITY_CODE = os.getenv("ENTITY_CODE", "MAIN")


def _resolve() -> tuple[str, str]:
    app = create_app()
    with app.app_context():
        tid = db.session.execute(text(
            "SELECT id FROM tenants WHERE code = :tc"), {"tc": TENANT_CODE}).scalar()
        if not tid:
            raise SystemExit(
                f"tenant {TENANT_CODE} not found — run scripts/seed_base.py first")
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(tid)})
        eid = db.session.execute(text(
            "SELECT id FROM entities WHERE tenant_id = :t AND code = :ec"
        ), {"t": str(tid), "ec": ENTITY_CODE}).scalar()
    if not eid:
        raise SystemExit(
            f"entity {ENTITY_CODE} not found for tenant {TENANT_CODE} — run scripts/seed_base.py")
    return str(tid), str(eid)


TID, EID = _resolve()
