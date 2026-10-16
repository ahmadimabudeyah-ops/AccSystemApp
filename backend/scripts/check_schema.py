"""Compare SQLAlchemy model columns against actual DB columns.

Usage:  python scripts/check_schema.py
Reports every model column missing from its table and every table column
not present in the model (informational).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import base as _base  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        insp = inspect(db.engine)
        tables = {t: set(c["name"] for c in insp.get_columns(t))
                  for t in insp.get_table_names() if not t.startswith("alembic")}

        missing = []      # (table, column) in model but not in DB
        orphan = []       # (table, column) in DB but not in model

        for mapper in _base.Base.registry.mappers:
            cls = mapper.class_
            table = getattr(cls, "__tablename__", None)
            if not table or table not in tables:
                continue
            model_cols = {c.name for c in mapper.columns}
            db_cols = tables[table]
            for c in sorted(model_cols - db_cols):
                missing.append((table, c))
            for c in sorted(db_cols - model_cols):
                orphan.append((table, c))

        print("=== MODEL COLUMNS MISSING FROM DB (must fix) ===")
        for t, c in missing:
            print(f"  {t}.{c}")
        print(f"  total: {len(missing)}")
        print("=== DB COLUMNS NOT IN MODEL (informational) ===")
        for t, c in orphan:
            print(f"  {t}.{c}")
        print(f"  total: {len(orphan)}")
        return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
