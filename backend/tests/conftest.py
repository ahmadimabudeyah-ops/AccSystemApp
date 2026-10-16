"""Pytest fixtures: app + DEMO tenant RLS context (local PostgreSQL :5433)."""
import os
import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://accounting:accounting123@127.0.0.1:5433/accounting_db",
)


@pytest.fixture()
def app():
    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def ctx(app):
    with app.app_context():
        from app.extensions import db
        from app.models.tenant import Tenant
        from sqlalchemy import text
        tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
        assert tenant, "DEMO tenant missing — run scripts/seed_base.py"
        db.session.execute(
            text("SET app.current_tenant_id = :t"), {"t": str(tenant.id)})
        yield
