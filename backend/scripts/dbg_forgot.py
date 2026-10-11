"""Debug tax-file + forgot in-process."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
c = app.test_client()
r = c.post("/api/v1/auth/forgot-password",
           json={"tenant_id": "DEMO", "username": "admin"},
           headers={"X-Tenant-ID": "b39787b5-52fb-4fb0-b41f-98b90b5853d6"})
print("FORGOT:", r.status_code, r.get_data(as_text=True)[:300])
