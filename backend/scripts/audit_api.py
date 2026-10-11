"""Deep audit sweep: exercise every API endpoint, report pass/fail."""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"
TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
EID = "f50db4a1-9381-400d-954b-79c515667f74"


def call(method, path, token=None, body=None, headers=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Tenant-ID", TID)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=20) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"html": True}


results = []


def check(name, cond, extra=""):
    results.append((name, "PASS" if cond else "FAIL", extra))


s, login = call("POST", "/api/v1/auth/login",
                body={"username": "admin", "password": "Admin@123"})
check("auth.login", s == 200, str(s))
tok = login.get("access_token", "")
s, me = call("GET", "/api/v1/auth/me", tok)
check("auth.me", s == 200, str(s))
s, _ = call("POST", "/api/v1/auth/refresh", tok)
check("auth.refresh-with-access (expect 422)", s == 422, str(s))

s, tenants = call("GET", "/api/v1/tenants", tok)
tdata = tenants.get("data", tenants) if isinstance(tenants, dict) else tenants
check("tenants.list", s == 200 and len(tdata) >= 1, str(s))
s, ents = call("GET", f"/api/v1/tenants/{TID}/entities", tok)
check("tenants.entities", s == 200, str(s))
s, br = call("GET", f"/api/v1/tenants/entities/{EID}/branches", tok)
check("tenants.branches", s == 200, str(s))

s, accs = call("GET", f"/api/v1/accounts?entity_id={EID}", tok)
check("accounts.list", s == 200 and len(accs.get("data", [])) > 0, str(s))
aid = accs["data"][0]["id"] if s == 200 else None
s, one = call("GET", f"/api/v1/accounts/{aid}", tok) if aid else (0, {})
check("accounts.detail", s == 200, str(s))
s, bad = call("GET", "/api/v1/accounts/00000000-0000-0000-0000-000000000000", tok)
check("accounts.404", s == 404, str(s))
s, noauth = call("GET", f"/api/v1/accounts?entity_id={EID}")
check("accounts.no-auth-401", s == 401, str(s))
s, notenant = call("GET", "/api/v1/accounts", tok,
                   headers={"X-Tenant-ID": ""})
check("accounts.no-tenant-note", s in (200, 400), str(s))

s, js = call("GET", "/api/v1/journals", tok)
check("journals.list", s == 200, str(s))
s, es = call("GET", "/api/v1/journal-entries", tok)
check("entries.list", s == 200, str(s))
eid = es["data"][0]["id"] if s == 200 and es.get("data") else None
s, det = call("GET", f"/api/v1/journal-entries/{eid}", tok) if eid else (0, {})
check("entries.detail", s == 200, str(s))
s, lines = call("GET", f"/api/v1/journal-entries/{eid}/lines", tok) if eid else (0, {})
check("entries.lines", s == 200 and len(lines.get("data", [])) > 0, str(s))

s, tb = call("GET", "/api/v1/reports/trial-balance?period_id=00000000-0000-0000-0000-000000000000", tok)
check("reports.tb-empty-period", s == 200 and tb["data"]["balanced"], str(s))
s, users = call("GET", "/api/v1/users", tok)
check("users.list", s == 200 and len(users.get("data", [])) >= 2, str(s))
s, roles = call("GET", "/api/v1/roles", tok)
check("roles.list", s == 200, str(s))

print(f"{'CHECK':50} RESULT")
for n, r, x in results:
    print(f"{n:50} {r} {x}")
print("FAILURES:", sum(1 for _, r, _ in results if r == "FAIL"))
