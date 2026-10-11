"""Debug biz endpoints via test client."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()
c = app.test_client()
r = c.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"},
           headers={"X-Tenant-ID": "b39787b5-52fb-4fb0-b41f-98b90b5853d6"})
tok = r.get_json()["access_token"]
h = {"X-Tenant-ID": "b39787b5-52fb-4fb0-b41f-98b90b5853d6", "Authorization": "Bearer " + tok}
r = c.post("/api/v1/exchange-rates", json={
    "from_currency": "USD", "to_currency": "JOD",
    "rate_date": "2026-01-31", "rate": 0.709}, headers=h)
print("FX:", r.status_code, r.get_data(as_text=True)[:400])
