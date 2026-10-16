"""Reproduce HTTP 500 on post via test client (full middleware + JWT stack)."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

from _ids import TID, EID  # noqa: E402
app = create_app()
app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=True)
c = app.test_client()
r = c.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"},
           headers={"X-Tenant-ID": TID})
tok = r.get_json()["access_token"]
h = {"X-Tenant-ID": TID, "Authorization": "Bearer " + tok}
# fresh draft with unique key
import uuid  # noqa: E402
r = c.post("/api/v1/journal-entries", json={
    "entity_id": "f50db4a1-9381-400d-954b-79c515667f74",
    "journal_id": "a61463e1-7405-48a4-84ea-704e7033c6ef",
    "document_date": "2026-01-07", "posting_date": "2026-01-07",
    "description": "t3", "source_event_key": "dbg." + uuid.uuid4().hex,
    "lines": [{"account_id": "2495f8aa-2444-46d6-aecb-2c1e2c377cb3", "debit": 10},
              {"account_id": "68f710f2-b44f-4612-a728-7b5096ec382b", "credit": 10}]}, headers=h)
print("CREATE:", r.status_code)
eid = r.get_json()["data"]["id"]
r = c.post(f"/api/v1/journal-entries/{eid}/post", headers=h)
print("POST:", r.status_code, (r.get_json() or {}))
