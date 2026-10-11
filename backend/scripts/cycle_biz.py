"""Business-layer verification: FX, approvals, schedules, portal, export, status, import."""
import io
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
EID = "f50db4a1-9381-400d-954b-79c515667f74"


def call(method, path, token=None, body="__none__", raw=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Tenant-ID", TID)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if raw is not None:
        data, ctype = raw
    elif body != "__none__":
        data, ctype = json.dumps(body).encode(), "application/json"
    else:
        data, ctype = None, None
    if data:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, data=data, timeout=25) as r:
            body_r = r.read().decode()
            try:
                return r.status, json.loads(body_r) if body_r else {}
            except Exception:
                return r.status, {"raw": True}
    except urllib.error.HTTPError as e:
        body_r = e.read().decode()
        try:
            return e.code, json.loads(body_r) if body_r else {}
        except Exception:
            return e.code, {"raw": body_r[:120]}


def login(u, p):
    s, d = call("POST", "/api/v1/auth/login", body={"username": u, "password": p})
    assert s == 200, d
    return d["access_token"]


admin = login("admin", "Admin@123")
checker = login("checker", "Checker@123")
results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


s, fx = call("POST", "/api/v1/exchange-rates", admin,
             {"from_currency": "USD", "to_currency": "JOD", "rate_date": "2026-01-31", "rate": 0.709})
check("fx-upsert", s in (200, 201), str(s))
s, cv = call("POST", "/api/v1/fx/convert", admin,
             {"amount": 1000, "from": "USD", "to": "JOD", "date": "2026-01-31"})
check("fx-convert", s == 200 and cv["data"]["amount"] == 709.0, str(cv))
s, per = call("GET", "/api/v1/fiscal-periods?entity_id=" + EID, admin)
pid = per["data"][0]["id"]
s, rv = call("POST", "/api/v1/fx/revalue", admin,
             {"entity_id": EID, "period_id": pid, "account_codes": ["102001"]})
check("fx-revalue", s == 201, str(s))
s, rules = call("GET", "/api/v1/approval-rules", admin)
existing = [r for r in rules.get("data", []) if r.get("doc_type") == "invoice"]
if not existing:
    s, rule = call("POST", "/api/v1/approval-rules", admin,
                   {"entity_id": EID, "doc_type": "invoice", "min_amount": 1000000,
                    "required_role": "FINANCE_MANAGER"})
    check("approval-rule-create", s == 201, str(s))
else:
    check("approval-rule-create", True, "exists")
s, sch = call("POST", "/api/v1/report-schedules", admin,
               {"entity_id": EID, "report_code": "trial-balance", "cron": "0 7 * * *"})
check("schedule-create", s == 201, str(s))
if s == 201:
    s, run = call("POST", f"/api/v1/report-schedules/{sch['data']['id']}/run", admin)
    check("schedule-run", s == 200, str(s))
s, fb = call("POST", "/api/v1/feedback", admin, {"subject": "t", "body": "b"})
check("feedback", s == 201, str(s))
s, parties = call("GET", "/api/v1/parties?entity_id=" + EID, admin)
party = parties["data"][0]["id"]
s, tok = call("POST", "/api/v1/portal-tokens", admin, {"party_id": party, "days": 7})
check("portal-token", s == 201 and tok["data"].get("token"), str(s))
if s == 201:
    req = urllib.request.Request(f"{BASE}/portal/{tok['data']['token']}")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        check("portal-view", r.status == 200, str(r.status))
    except Exception as e:
        check("portal-view", False, repr(e)[:100])
s, exp = call("GET", "/api/v1/export/tenant", admin)
check("export", s == 200 and len(exp["data"]["accounts"]) > 40, str(s))
s, st = call("GET", "/api/v1/status", admin)
check("status", s == 200 and st["data"]["db"] == "up", str(s))
s, parts = call("GET", "/api/v1/parties?entity_id=" + EID, admin)
check("parties-typed", s == 200 and all("types" in p for p in parts["data"]), str(s))
print("FAILURES:", results.count(False))
raise SystemExit(1 if False in results else 0)
