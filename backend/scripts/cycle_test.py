"""Full accounting cycle: maker creates -> checker posts -> trial balance -> reverse.

Usage: python scripts/cycle_test.py
Exit nonzero on any failure. Idempotent keys use a fresh uuid per run.
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

BASE = "http://127.0.0.1:5000"
TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
EID = "f50db4a1-9381-400d-954b-79c515667f74"


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Tenant-ID", TID)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=20) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {"raw": raw[:200]}
        except Exception:
            return e.code, {"raw": raw[:200]}


def login(username, password):
    s, data = call("POST", "/api/v1/auth/login",
                   body={"username": username, "password": password})
    assert s == 200, data
    return data["access_token"]


admin = login("admin", "Admin@123")
checker = login("checker", "Checker@123")
print("LOGIN_OK admin+checker")

s, journals = call("GET", "/api/v1/journals", checker)
jid = next(j["id"] for j in journals["data"] if j["code"] == "GEN")
s, accs = call("GET", f"/api/v1/accounts?entity_id={EID}&q=101001", checker)
cash = accs["data"][0]["id"]
s, accs = call("GET", f"/api/v1/accounts?entity_id={EID}&q=4010", checker)
rev = accs["data"][0]["id"]

key = "cycle." + uuid.uuid4().hex[:8]
s, entry = call("POST", "/api/v1/journal-entries", checker, {
    "entity_id": EID, "journal_id": jid, "document_date": "2026-01-08",
    "posting_date": "2026-01-08", "description": "cycle test",
    "source_event_key": key,
    "lines": [{"account_id": cash, "debit": 116},
              {"account_id": rev, "credit": 100},
              {"account_id": rev, "credit": 16}]})
assert s == 201, entry
eid = entry["data"]["id"]
print("CREATE_OK", eid)

s, dup = call("POST", "/api/v1/journal-entries", checker, {
    "entity_id": EID, "journal_id": jid, "document_date": "2026-01-08",
    "posting_date": "2026-01-08", "description": "cycle test",
    "source_event_key": key,
    "lines": [{"account_id": cash, "debit": 116},
              {"account_id": rev, "credit": 100},
              {"account_id": rev, "credit": 16}]})
assert s == 200 and dup["error"]["code"] == "DUPLICATE_EVENT", dup
print("IDEMPOTENCY_OK replay -> 200 DUPLICATE_EVENT")

s, self_post = call("POST", f"/api/v1/journal-entries/{eid}/post", checker)
assert s == 403, self_post
print("SEGREGATION_OK maker cannot post own entry")

s, posted = call("POST", f"/api/v1/journal-entries/{eid}/post", admin)
assert s == 200 and posted["data"]["status"] == "posted", posted
print("POST_OK", posted["data"]["official_number"])

s, tb = call("GET", "/api/v1/reports/trial-balance?period_id=" + posted["data"]["period_id"], admin)
assert s == 200 and tb["data"]["balanced"] and tb["data"]["total_debit"] > 0, tb
print("TRIAL_BALANCE_OK total =", tb["data"]["total_debit"])

s, rev_entry = call("POST", f"/api/v1/journal-entries/{eid}/reverse", admin, {
    "reason": "cycle test reversal", "reversal_date": "2026-01-09"})
assert s == 201 and rev_entry["data"]["status"] == "posted", rev_entry
print("REVERSAL_OK", rev_entry["data"]["id"])
print("CYCLE_OK")
