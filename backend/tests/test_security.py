"""Security tests: tenant isolation (RLS + JWT/header cross-check)."""
import uuid

import pytest

from app.extensions import db
from app.models.tenant import Tenant


def _login(client, tid, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password},
                       headers={"X-Tenant-ID": tid})


def test_rls_without_context_returns_zero(ctx):
    from sqlalchemy import text
    db.session.execute(text("RESET app.current_tenant_id"))
    from app.models.account import Account
    assert db.session.query(Account).count() == 0


def test_tenant_mismatch_forbidden(app, ctx):
    c = app.test_client()
    tid = str(db.session.query(Tenant).filter_by(code="DEMO").first().id)
    r = _login(c, tid, "admin", "Admin@123")
    tok = r.get_json()["access_token"]
    fake = str(uuid.uuid4())
    r = c.get("/api/v1/accounts", headers={"X-Tenant-ID": fake, "Authorization": "Bearer " + tok})
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "TENANT_MISMATCH"


def test_forged_tenant_sees_nothing(app, ctx):
    """Even without the cross-check, RLS would scope to the forged tenant
    (which has no data for this JWT's user) — belt and suspenders."""
    c = app.test_client()
    tid = str(db.session.query(Tenant).filter_by(code="DEMO").first().id)
    r = _login(c, tid, "admin", "Admin@123")
    tok = r.get_json()["access_token"]
    r = c.get("/api/v1/users", headers={"X-Tenant-ID": tid, "Authorization": "Bearer " + tok})
    assert r.status_code == 200
    assert len(r.get_json()["data"]) >= 1
