"""Debug portal view end to end."""
import hashlib
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()
c = app.test_client()
TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
r = c.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"},
           headers={"X-Tenant-ID": TID})
tok = r.get_json()["access_token"]
h = {"X-Tenant-ID": TID, "Authorization": "Bearer " + tok}
r = c.get("/api/v1/parties", headers=h)
pid = r.get_json()["data"][0]["id"]
r = c.post("/api/v1/portal-tokens", json={"party_id": pid}, headers=h)
print("TOKEN:", r.status_code)
raw = r.get_json()["data"]["token"]
r = c.get(f"/portal/{raw}")
body = r.get_data(as_text=True)
print("VIEW:", r.status_code)
import re
m = re.search(r"<h1>(.*?)</h1>", body)
print("H1:", m.group(1) if m else body[2000:2400])
from app.extensions import db as _db
from sqlalchemy import text as _text
with c.application.app_context():
    h = hashlib.sha256(raw.encode()).hexdigest()
    print("HASH:", h[:16])
    row = _db.session.execute(_text("SELECT * FROM portal_resolve(:h)"), {"h": h}).first()
    print("ROW:", row)
    n = _db.session.execute(_text("SELECT count(*) FROM portal_tokens")).scalar()
    print("COUNT_NORLS:", n)
