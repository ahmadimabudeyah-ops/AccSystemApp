"""Income-tax bracket API + progressive calculation.

Run:  pytest tests/test_tax_brackets.py -v
Needs: seeded local PG (scripts/seed_base.py + seed_demo2.py wrote the 2026 slabs).
"""
import pytest

from app.extensions import db
from app.models.tenant import Tenant
from app.services.payroll_service import annual_tax


@pytest.fixture()
def env(ctx):
    tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
    assert tenant, "DEMO tenant missing — run scripts/seed_base.py"
    return {"tenant": tenant, "tid": str(tenant.id)}


def _headers(env):
    return {"X-Tenant-ID": env["tid"]}


def _login(client, env):
    rv = client.post("/api/v1/auth/login",
                     json={"username": "admin", "password": "Admin@123"},
                     headers=_headers(env))
    assert rv.status_code == 200, rv.get_json()
    tok = rv.get_json()["access_token"]
    return {**_headers(env), "Authorization": "Bearer " + tok}


# --------------------------------------------------------------- pure math
def test_annual_tax_is_progressive(env):
    """Marginal rates, not a flat rate: 30,000 JOD must not pay 20% of 30,000."""
    t = env["tid"]
    assert annual_tax(9000, 2026, t) == 0.0          # exactly the exemption
    assert annual_tax(14000, 2026, t) == 250.0       # 5,000 x 5%
    assert annual_tax(19000, 2026, t) == 750.0       # +5,000 x 10%
    assert annual_tax(24000, 2026, t) == 1500.0      # +5,000 x 15%
    assert annual_tax(30000, 2026, t) == 2700.0      # +6,000 x 20%
    assert annual_tax(40000, 2026, t) == 4700.0
    assert annual_tax(60000, 2026, t) == 8700.0


def test_annual_tax_below_exemption_is_zero(env):
    t = env["tid"]
    assert annual_tax(0, 2026, t) == 0.0
    assert annual_tax(5000, 2026, t) == 0.0
    assert annual_tax(8999.999, 2026, t) == 0.0


def test_annual_tax_is_monotonic(env):
    t = env["tid"]
    prev = -1
    for amount in range(9000, 80000, 2500):
        tax = annual_tax(amount, 2026, t)
        assert tax >= prev, (amount, tax, prev)
        assert tax >= 0
        prev = tax


# ------------------------------------------------------------------ API
def test_brackets_list(app, client, env):
    with app.app_context():
        rv = client.get("/api/v1/hr/income-tax-brackets", headers=_login(client, env))
        assert rv.status_code == 200, rv.get_json()
        rows = rv.get_json()["data"]
        assert rows, "no 2026 brackets seeded — run seed_demo2.py"
        years = {r["year"] for r in rows}
        assert 2026 in years
        for r in rows:
            assert r["rate"] > 0
            assert r["from_amount"] >= 0
            if r["to_amount"] is not None:
                assert r["to_amount"] > r["from_amount"]


def test_brackets_simulate(app, client, env):
    with app.app_context():
        h = _login(client, env)
        rv = client.post("/api/v1/hr/income-tax-brackets/simulate",
                         json={"year": 2026, "annual_amounts": [30000]}, headers=h)
        assert rv.status_code == 200
        row = rv.get_json()["data"]["rows"][0]
        assert row["annual_taxable"] == 30000
        assert row["tax"] == 2700.0


def test_brackets_create_update_roundtrip(app, client, env):
    """A tax review changes data, not code: PUT a slab, then delete it."""
    with app.app_context():
        h = _login(client, env)
        rv = client.post("/api/v1/hr/income-tax-brackets", json={
            "year": 2030, "from_amount": 0, "to_amount": 1000, "rate": 1.5}, headers=h)
        assert rv.status_code == 201, rv.get_json()
        bid = rv.get_json()["data"]["id"]
        rv = client.put(f"/api/v1/hr/income-tax-brackets/{bid}",
                        json={"rate": 2.5}, headers=h)
        assert rv.status_code == 200
        assert rv.get_json()["data"]["rate"] == 2.5
        # unknown id -> 404, never 500
        rv = client.put("/api/v1/hr/income-tax-brackets/"
                        "00000000-0000-0000-0000-000000000000",
                        json={"rate": 3}, headers=h)
        assert rv.status_code == 404
        # clean up so the table stays pristine for the client demo
        from sqlalchemy import text as _text
        db.session.execute(_text(
            "DELETE FROM income_tax_brackets WHERE tenant_id=:t AND year=2030"),
            {"t": env["tid"]})
        db.session.commit()
        rv = client.get("/api/v1/hr/income-tax-brackets?year=2030", headers=h)
        assert rv.get_json()["data"] == []


def test_brackets_require_auth(app, client, env):
    """No token -> rejected. The tenant middleware answers 400 (missing
    X-Tenant-ID) before @jwt_required can answer 401, so accept either."""
    with app.app_context():
        rv = client.get("/api/v1/hr/income-tax-brackets")
        assert rv.status_code in (400, 401), rv.status_code
        rv = client.post("/api/v1/hr/income-tax-brackets", json={})
        assert rv.status_code in (400, 401), rv.status_code
        # tenant present but token missing -> 401
        rv = client.get("/api/v1/hr/income-tax-brackets", headers=_headers(env))
        assert rv.status_code == 401, rv.status_code
        # malformed token -> flask-jwt-extended answers 422 (still rejected)
        bad = {**_headers(env), "Authorization": "Bearer not-a-real-token"}
        rv = client.get("/api/v1/hr/income-tax-brackets", headers=bad)
        assert rv.status_code in (401, 422), rv.status_code
