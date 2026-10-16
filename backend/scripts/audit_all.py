"""Full route sweep: every API GET + every web page against the LIVE server.

Usage:  python scripts/audit_all.py
Requires: server on :5000 (or $BASE_PORT), seeded DEMO tenant.

Strategy
  * Enumerate the Flask url_map (authoritative source of truth for routes).
  * Substitute real ids pulled from the database for every path parameter.
  * Issue an authenticated GET for every api route and every web page.
  * Report PASS / FAIL per route plus a module summary.

400/404 on detail routes whose id does not exist in this dataset are reported
as INFO, not failures.  Only 5xx and connection errors count as failures.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, ".")
from _ids import TID, EID  # noqa: E402

BASE = "http://127.0.0.1:" + os.getenv("BASE_PORT", "5000")
NIL = "00000000-0000-0000-0000-000000000000"


def call(method, path, token=None, body=None, headers=None, retries=2):
    for attempt in range(retries + 1):
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
            with urllib.request.urlopen(req, data=data, timeout=30) as r:
                raw = r.read().decode()
                try:
                    return r.status, json.loads(raw) if raw else {}
                except (json.JSONDecodeError, ValueError):
                    return r.status, {"html": True, "len": len(raw)}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw) if raw else {}
            except (json.JSONDecodeError, ValueError):
                return e.code, {"html": True, "len": len(raw)}
        except Exception as e:  # noqa: BLE001
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return 0, {"err": str(e)[:160]}
    return 0, {"err": "unreachable"}


def build_id_pool() -> dict[str, str]:
    from sqlalchemy import text  # noqa: E402
    from app import create_app  # noqa: E402
    from app.extensions import db  # noqa: E402

    app = create_app()
    with app.app_context():
        def q(sql, **kw):
            for _attempt in range(2):
                try:
                    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
                    row = db.session.execute(text(sql), kw).first()
                    return str(row[0]) if row else None
                except Exception:  # noqa: BLE001
                    db.session.rollback()
            return None

        pool = {
            "tenant_id": TID, "entity_id": EID,
            "acc_id": q("SELECT id FROM accounts WHERE entity_id=:e LIMIT 1", e=EID),
            "account_id": q("SELECT id FROM accounts WHERE entity_id=:e LIMIT 1", e=EID),
            "j_id": q("SELECT id FROM journals WHERE entity_id=:e LIMIT 1", e=EID),
            "journal_id": q("SELECT id FROM journals WHERE entity_id=:e LIMIT 1", e=EID),
            "e_id": q("SELECT id FROM journal_entries WHERE entity_id=:e LIMIT 1", e=EID),
            "entry_id": q("SELECT id FROM journal_entries WHERE entity_id=:e LIMIT 1", e=EID),
            "period_id": q("SELECT id FROM fiscal_periods WHERE entity_id=:e LIMIT 1", e=EID),
            "pid": q("SELECT id FROM fiscal_periods WHERE entity_id=:e LIMIT 1", e=EID),
            "p_id": q("SELECT id FROM parties WHERE entity_id=:e LIMIT 1", e=EID),
            "party_id": q("SELECT id FROM parties WHERE entity_id=:e LIMIT 1", e=EID),
            "customer_id": q("SELECT id FROM parties WHERE entity_id=:e AND party_type='customer' LIMIT 1", e=EID),
            "supplier_id": q("SELECT id FROM parties WHERE entity_id=:e AND party_type='supplier' LIMIT 1", e=EID),
            "prod_id": q("SELECT id FROM products WHERE entity_id=:e LIMIT 1", e=EID),
            "product_id": q("SELECT id FROM products WHERE entity_id=:e LIMIT 1", e=EID),
            "o_id": q("SELECT id FROM sales_orders WHERE entity_id=:e LIMIT 1", e=EID),
            "q_id": q("SELECT id FROM quotations WHERE entity_id=:e LIMIT 1", e=EID),
            "d_id": q("SELECT id FROM deliveries WHERE entity_id=:e LIMIT 1", e=EID),
            "i_id": q("SELECT id FROM invoices WHERE entity_id=:e LIMIT 1", e=EID),
            "invoice_id": q("SELECT id FROM invoices WHERE entity_id=:e LIMIT 1", e=EID),
            "g_id": q("SELECT id FROM purchase_requests WHERE entity_id=:e LIMIT 1", e=EID),
            "b_id": q("SELECT id FROM purchase_orders WHERE entity_id=:e LIMIT 1", e=EID),
            "c_id": q("SELECT id FROM goods_receipts WHERE entity_id=:e LIMIT 1", e=EID),
            "bill_id": q("SELECT id FROM bills WHERE entity_id=:e LIMIT 1", e=EID),
            "a_id": q("SELECT id FROM assets WHERE entity_id=:e LIMIT 1", e=EID),
            "asset_id": q("SELECT id FROM assets WHERE entity_id=:e LIMIT 1", e=EID),
            "r_id": q("SELECT id FROM cash_boxes WHERE entity_id=:e LIMIT 1", e=EID),
            "box_id": q("SELECT id FROM cash_boxes WHERE entity_id=:e LIMIT 1", e=EID),
            "w_id": q("SELECT id FROM warehouses WHERE entity_id=:e LIMIT 1", e=EID),
            "warehouse_id": q("SELECT id FROM warehouses WHERE entity_id=:e LIMIT 1", e=EID),
            "u_id": q("SELECT id FROM users WHERE tenant_id=:t LIMIT 1", t=TID),
            "user_id": q("SELECT id FROM users WHERE tenant_id=:t LIMIT 1", t=TID),
            "role_id": q("SELECT id FROM roles WHERE tenant_id=:t LIMIT 1", t=TID),
            "emp_id": q("SELECT id FROM employees WHERE entity_id=:e LIMIT 1", e=EID),
            "employee_id": q("SELECT id FROM employees WHERE entity_id=:e LIMIT 1", e=EID),
            "student_id": q("SELECT id FROM students WHERE entity_id=:e LIMIT 1", e=EID),
            "project_id": q("SELECT id FROM projects WHERE entity_id=:e LIMIT 1", e=EID),
            "budget_id": q("SELECT id FROM budgets WHERE entity_id=:e LIMIT 1", e=EID),
            "bank_id": q("SELECT id FROM bank_accounts WHERE entity_id=:e LIMIT 1", e=EID),
            "check_id": q("SELECT id FROM checks WHERE entity_id=:e LIMIT 1", e=EID),
            "transfer_id": q("SELECT id FROM cash_transfers WHERE entity_id=:e LIMIT 1", e=EID),
            "count_id": q("SELECT id FROM stock_counts WHERE entity_id=:e LIMIT 1", e=EID),
            "category_id": q("SELECT id FROM product_categories WHERE entity_id=:e LIMIT 1", e=EID),
            "tax_id": q("SELECT id FROM taxes WHERE code='VAT16' LIMIT 1"),
            "dimension_id": q("SELECT id FROM dimensions WHERE entity_id=:e LIMIT 1", e=EID),
            "payroll_run_id": q("SELECT id FROM payroll_runs WHERE entity_id=:e LIMIT 1", e=EID),
            "leave_id": q("SELECT id FROM leave_requests WHERE entity_id=:e LIMIT 1", e=EID),
            "advance_id": q("SELECT id FROM employee_loans WHERE entity_id=:e LIMIT 1", e=EID),
            "contract_id": q("SELECT id FROM fee_contracts WHERE entity_id=:e LIMIT 1", e=EID),
            "term_id": q("SELECT id FROM payment_terms WHERE entity_id=:e LIMIT 1", e=EID),
            "match_id": q("SELECT id FROM bill_matches WHERE entity_id=:e LIMIT 1", e=EID),
            "return_id": q("SELECT id FROM customer_returns WHERE entity_id=:e LIMIT 1", e=EID),
            "cn_id": q("SELECT id FROM credit_notes WHERE entity_id=:e LIMIT 1", e=EID),
            "payment_id": q("SELECT id FROM customer_payments WHERE entity_id=:e LIMIT 1", e=EID),
            "bp_id": q("SELECT id FROM bank_statement_lines WHERE entity_id=:e LIMIT 1", e=EID),
            "line_id": q("SELECT id FROM journal_lines WHERE entity_id=:e LIMIT 1", e=EID),
            "name": "trial-balance", "t_id": "VAT16", "token": "x",
        }
    return {k: v for k, v in pool.items() if v}


PARAM_RE = re.compile(r"<(?:uuid:)?([a-z_]+)>")


def fill(url: str, pool: dict[str, str]) -> str | None:
    def sub(m):
        key = m.group(1)
        if key in pool:
            return pool[key]
        for k, v in pool.items():
            if k.startswith(key) or k.endswith("_" + key):
                return v
        return NIL
    out = PARAM_RE.sub(sub, url)
    out = (out.replace("<token>", "x").replace("<t_id>", "VAT16")
              .replace("<name>", "trial-balance"))
    return None if "<" in out else out


def main() -> int:
    from app import create_app  # noqa: E402

    app = create_app()
    pool = build_id_pool()
    s, login = call("POST", "/api/v1/auth/login",
                    body={"username": "admin", "password": "Admin@123"})
    if s != 200:
        print("LOGIN FAILED", login)
        return 2
    token = login["access_token"]

    api_rows, web_rows = [], []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static" or "GET" not in rule.methods:
            continue
        url = fill(str(rule), pool)
        if url is None:
            continue
        s, _ = call("GET", url, token)
        entry = {"rule": str(rule), "url": url, "status": s}
        (api_rows if str(rule).startswith("/api/") else web_rows).append(entry)

    def is_fail(r):
        return r["status"] == 0 or r["status"] >= 500

    api_fail = [r for r in api_rows if is_fail(r)]
    web_fail = [r for r in web_rows if is_fail(r)]
    api_info = [r for r in api_rows if r["status"] in (400, 404) and not is_fail(r)]

    print(f"API ROUTES : {len(api_rows):4d}  OK: {len(api_rows)-len(api_fail)-len(api_info):4d}  "
          f"INFO(400/404): {len(api_info):3d}  FAIL: {len(api_fail)}")
    for r in api_fail:
        print(f"   FAIL [{r['status']}] {r['url']}")
    print(f"WEB PAGES  : {len(web_rows):4d}  OK: {len(web_rows)-len(web_fail):4d}  FAIL: {len(web_fail)}")
    for r in web_fail:
        print(f"   FAIL [{r['status']}] {r['url']}")
    print("TOTAL FAILURES:", len(api_fail) + len(web_fail))
    return 1 if (api_fail or web_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
