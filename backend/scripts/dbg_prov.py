"""Debug provision via test client."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()
c = app.test_client()
r = c.post("/api/v1/tenants/provision", json={
    "code": "TRIAL1", "name_ar": "شركة تجريبية",
    "admin_email": "boss@trial1.local", "admin_password": "Trial@123"})
print(r.status_code, r.get_data(as_text=True)[:600])
