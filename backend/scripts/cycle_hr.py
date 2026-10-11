"""HR + education + projects cycle via HTTP."""
import json
import urllib.request
import urllib.error

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


def login(u, p):
    s, d = call("POST", "/api/v1/auth/login", body={"username": u, "password": p})
    assert s == 200, d
    return d["access_token"]


admin = login("admin", "Admin@123")
checker = login("checker", "Checker@123")

s, emps = call("GET", "/api/v1/hr/employees?entity_id=" + EID, admin)
assert s == 200 and len(emps["data"]) >= 3, emps
print("EMPLOYEES_OK", len(emps["data"]))
s, pers = call("GET", "/api/v1/fiscal-periods?entity_id=" + EID, admin)
pid = next(p["id"] for p in pers["data"] if p["code"] == "2026-01")
s, run = call("POST", "/api/v1/hr/payroll-runs", checker, {
    "entity_id": EID, "fiscal_period_id": pid, "pay_month": "2026-01-15"})
assert s == 201 and run["data"]["total_net"] > 0, run
print("RUN_OK net =", run["data"]["total_net"])
rid = run["data"]["id"]
s, det = call("GET", f"/api/v1/hr/payroll-runs/{rid}", admin)
assert s == 200 and len(det["data"]["payslips"]) >= 3, det
print("PAYSLIPS_OK")
s, posted = call("POST", f"/api/v1/hr/payroll-runs/{rid}/post", admin)
assert s == 200, posted
print("PAYROLL_POST_OK", posted["data"]["entry_id"][:8])

s, students = call("GET", "/api/v1/education/students?entity_id=" + EID, admin)
assert s == 200 and students["data"], students
sid = students["data"][0]["id"]
s, contracts = call("GET", "/api/v1/education/fee-contracts", admin)
existing = [c for c in contracts.get("data", []) if c.get("academic_year") == "2026"]
if existing:
    cid = existing[0]["id"]
    print("FEE_CONTRACT_EXISTS", cid)
else:
    s, contract = call("POST", "/api/v1/education/fee-contracts", checker, {
        "entity_id": EID, "student_id": sid, "academic_year": "2026",
        "total_fees": 3000, "discount_pct": 10, "installments": 3})
    assert s == 201 and contract["data"]["net_fees"] == 2700.0, contract
    cid = contract["data"]["id"]
    print("FEE_CONTRACT_OK")
s, cpost = call("POST", f"/api/v1/education/fee-contracts/{cid}/post", admin)
assert s == 200, cpost
s, cdet = call("GET", f"/api/v1/education/fee-contracts/{cid}", admin)
open_insts = [i for i in cdet["data"]["installments"]
              if i["amount"] - i["paid_amount"] > 0.001]
if open_insts:
    iid = open_insts[0]["id"]
    amt = round(open_insts[0]["amount"] - open_insts[0]["paid_amount"], 3)
    s, pay = call("POST", f"/api/v1/education/fee-installments/{iid}/pay", checker, {"amount": amt})
    assert s == 201, pay
    print("FEE_PAY_OK")
else:
    print("FEE_PAY_SKIPPED already paid")

s, projs = call("GET", "/api/v1/projects", admin)
assert s == 200 and projs["data"], projs
prj = projs["data"][0]["id"]
s, cost = call("POST", f"/api/v1/projects/{prj}/costs", checker,
               {"amount": 5000, "description": "test cost"})
assert s == 201, cost
s, budgets = call("GET", "/api/v1/budgets", admin)
bid = budgets["data"][0]["id"]
s, var = call("GET", f"/api/v1/budgets/{bid}/variance", admin)
assert s == 200 and len(var["data"]["lines"]) >= 3, var
print("BUDGET_VARIANCE_OK lines =", len(var["data"]["lines"]))
s, audit = call("GET", "/api/v1/audit-logs", admin)
assert s == 200 and len(audit["data"]) > 0, audit
print("AUDIT_OK entries =", len(audit["data"]))
print("HR_EDU_PROJECTS_OK")
