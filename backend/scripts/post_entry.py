"""Post an entry as admin + trial balance. Usage: python scripts/post_entry.py <entry_id>"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"


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


s, login = call("POST", "/api/v1/auth/login",
                body={"username": "admin", "password": "Admin@123"})
assert s == 200, login
tok = login["access_token"]
eid = sys.argv[1]
s, posted = call("POST", f"/api/v1/journal-entries/{eid}/post", tok)
print("POST:", s, (posted.get("data") or {}).get("official_number"),
      (posted.get("data") or {}).get("status"), posted.get("error"))
