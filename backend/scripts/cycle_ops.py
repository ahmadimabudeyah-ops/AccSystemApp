"""Verify newly added endpoints (batch 2)."""
import json
import urllib.request
import urllib.error

import os as _os
BASE = "http://127.0.0.1:" + _os.getenv("BASE_PORT", "5000")
from _ids import TID, EID  # noqa: E402



def call(method, path, token=None, body="__none__"):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Tenant-ID", TID)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = None
    if body != "__none__":
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=20) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {"raw": raw[:120]}
        except Exception:
            return e.code, {"raw": raw[:120]}


def login(u, p):
    s, d = call("POST", "/api/v1/auth/login", body={"username": u, "password": p})
    assert s == 200, d
    return d["access_token"]


admin = login("admin", "Admin@123")
checker = login("checker", "Checker@123")
results = []


def check(name, cond, extra=""):
    results.append(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


s, oapi = call("GET", "/api/v1/openapi.json", admin)
check("openapi", s == 200 and len(oapi.get("paths", {})) > 100, str(len(oapi.get("paths", {}))))
s, cf = call("GET", f"/api/v1/reports/cash-flow?entity_id={EID}", admin)
check("cash-flow", s == 200 and "totals" in cf.get("data", {}), str(s))
s, taxes = call("GET", "/api/v1/taxes", admin)
vat = next(t["id"] for t in taxes["data"] if t["code"] == "VAT16")
s, tr = call("POST", "/api/v1/tax-returns/file", admin,
             {"entity_id": EID, "tax_id": vat, "period_code": "2026-01"})
check("tax-file", s in (200, 201, 409) and (s != 200 or tr["data"]["status"] == "filed"), str(s))
s, accts = call("GET", "/api/v1/treasury/bank-accounts", admin)
if accts.get("data"):
    ba = accts["data"][0]["id"]
    s, imp = call("POST", "/api/v1/treasury/bank-statements/import", checker, {
        "bank_account_id": ba, "stmt_date": "2026-01-31",
        "lines": [{"date": "2026-01-06", "description": "test line", "amount": 116}]})
    check("stmt-import", s == 201, str(s))
    if s == 201:
        sid = imp["data"]["id"]
        print("STMT_MATCHED =", imp["data"].get("matched"))
else:
    print("SKIP stmt-import (no bank account)")
s, rec = call("GET", "/api/v1/recurring-entries", admin)
check("recurring-list", s == 200, str(s))
s, notif = call("POST", "/api/v1/notifications", admin,
                {"title": "test", "body": "hello"})
check("notify-create", s == 201, str(s))
s, nl = call("GET", "/api/v1/notifications?unread=1", admin)
check("notify-list", s == 200 and len(nl["data"]) >= 1, str(s))
s, fg = call("POST", "/api/v1/auth/forgot-password",
             body={"tenant_id": "DEMO", "username": "admin"})
check("forgot", s == 200, str(s))
s, invs = call("GET", "/api/v1/sales/invoices", admin)
iid = invs["data"][0]["id"]
s, dsp = call("POST", f"/api/v1/sales/invoices/{iid}/dispute", admin)
check("dispute", s in (200, 409), str(s))
s, emp = call("GET", "/api/v1/hr/employees?entity_id=" + EID, admin)
import uuid as _uuid
s, tmp = call("POST", "/api/v1/hr/employees", admin, {
    "entity_id": EID, "employee_no": "E-TMP-" + _uuid.uuid4().hex[:6],
    "full_name_ar": "ظ…ظˆط¸ظپ ظ…ط¤ظ‚طھ",
    "hire_date": "2026-01-01", "basic_salary": 500})
assert s == 201, tmp
eid_ = tmp["data"]["id"]
s, term = call("POST", f"/api/v1/hr/employees/{eid_}/terminate", admin, {})
check("terminate", s == 200, str(s))
print("FAILURES:", results.count(False))
sys_exit = 1 if False in results else 0
raise SystemExit(sys_exit)
