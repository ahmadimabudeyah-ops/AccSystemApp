"""Alembic migration environment.

The blessed path for schema changes is the explicit SQL in ../db/sql/, but the
Python migrations are kept runnable so `flask db upgrade` works too.

Key points
  * Metadata comes from the declarative Base in app/models (note: NOT
    db.Model — the project's models register on their own Base, which is why
    this file imports Base rather than using db.metadata).
  * RLS is enabled + forced on nearly every table, so autogenerate must run
    with the tenant GUC set (see `_tenant()` below) or it silently sees no
    tables.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.base import Base  # noqa: E402
import app.models  # noqa: F401,E402 — registers every mapper on Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the models is not enough: the Flask app must be built so that
# Flask-SQLAlchemy binds the engine from config (DATABASE_URL / .env).
_flask_app = create_app()
config.set_main_option("sqlalchemy.url", _flask_app.config["SQLALCHEMY_DATABASE_URI"])

target_metadata = Base.metadata

EXCLUDE_TABLES = {"alembic_version"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True


def _tenant() -> str | None:
    """Return the first tenant id so RLS-protected tables are visible."""
    try:
        with db.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT id FROM tenants ORDER BY created_at LIMIT 1")).first()
        return str(row[0]) if row else None
    except Exception:  # noqa: BLE001
        return None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    tid = _tenant()
    if tid:
        @event.listens_for(connectable, "connect")
        def _set_tenant(dbapi_conn, _rec):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("SET app.current_tenant_id = %s", (tid,))
            cur.close()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
