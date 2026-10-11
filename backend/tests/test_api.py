"""API integration tests: auth -> accounts -> entry -> post -> trial balance.

Run:  pytest tests/test_api.py -v   (needs seeded local PG + JWT secret)
"""
import pytest


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client):
    rv = client.post("/api/v1/auth/login",
                     json={"username": "admin", "password": "Admin@123"},
                     headers={"X-Tenant-ID": "DEMO-TENANT-ID"})
    return rv


def test_health(client):
    assert client.get("/health").status_code == 200


def test_login_requires_tenant(client):
    rv = client.post("/api/v1/auth/login", json={"username": "x", "password": "y"})
    assert rv.status_code == 400
