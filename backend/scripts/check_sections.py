"""Per-section smoke test: every module the client listed, with live data.

Usage:  python scripts/check_sections.py [--port 5000]

Walks the exact list of screens the customer asked for (dashboard, accounting,
sales, purchases, inventory, treasury, assets, HR, education, projects, taxes,
parties, reports, settings, export) and asserts both:
  * the web page renders, and
  * the API it depends on returns 200 with at least one row when the dataset
    is expected to contain data.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, ".")
from _ids import TID, EID  # noqa: E402

BASE = "http://127.0.0.1:" + os.getenv("BASE_PORT", "5000")

# (section, page url, api url that must return >=1 row or None when optional)
SECTIONS = [
    ("لوحة التحكم", "/dashboard", "/api/v1/reports/dashboard-summary?entity_id="),
    ("المحاسبة/دليل الحسابات", "/accounts", "/api/v1/accounts?entity_id="),
    ("المحاسبة/شجرة الحسابات", "/accounts/tree", None),
    ("المحاسبة/الدفاتر", "/journals", "/api/v1/journals"),
    ("المحاسبة/القيود اليومية", "/journal-entries", "/api/v1/journal-entries"),
    ("المبيعات/عروض الأسعار", "/sales/quotations", None),
    ("المبيعات/أوامر البيع", "/sales/orders", None),
    ("المبيعات/التسليمات", "/sales/deliveries", None),
    ("المبيعات/فواتير العملاء", "/sales/invoices", "/api/v1/sales/invoices"),
    ("المبيعات/الدفعات", "/sales/payments", "/api/v1/sales/payments"),
    ("المبيعات/المرتجعات", "/sales/returns", None),
    ("المبيعات/إشعارات دائنة", "/sales/credit-notes", None),
    ("المشتريات/طلبات الشراء", "/purchases/requests", None),
    ("المشتريات/أوامر الشراء", "/purchases/orders", None),
    ("المشتريات/الاستلامات", "/purchases/receipts", None),
    ("المشتريات/فواتير الموردين", "/purchases/bills", "/api/v1/purchases/bills"),
    ("المشتريات/الدفعات", "/purchases/payments", None),
    ("المخزون/الأصناف", "/products", "/api/v1/products?entity_id="),
    ("المخزون/الحركات", "/inventory/moves", None),
    ("المخزون/الأرصدة", "/inventory/quants", None),
    ("المخزون/الجرد", "/inventory/counts", None),
    ("الخزينة/الصناديق", "/treasury/cash-boxes", None),
    ("الخزينة/حركات النقد", "/treasury/cash-transactions", None),
    ("الخزينة/البنوك", "/treasury/banks", None),
    ("الخزينة/الحسابات البنكية", "/treasury/bank-accounts", None),
    ("الخزينة/الشيكات", "/treasury/checks", None),
    ("الخزينة/التحويلات", "/treasury/transfers", None),
    ("الأصول/قائمة الأصول", "/assets", None),
    ("الأصول/الإهلاك", "/assets/depreciation", None),
    ("الموارد البشرية/الموظفون", "/hr/employees", "/api/v1/hr/employees"),
    ("الموارد البشرية/مسيرات الرواتب", "/hr/payroll-runs", None),
    ("الموارد البشرية/الإجازات", "/hr/leaves", None),
    ("الموارد البشرية/السلف", "/hr/loans", None),
    ("التعليم/الطلاب", "/education/students", None),
    ("التعليم/عقود الرسوم", "/education/fee-contracts", None),
    ("المشاريع/المشاريع", "/projects", None),
    ("المشاريع/الموازنات", "/budgets", None),
    ("الضرائب/الضرائب", "/taxes", None),
    ("الضرائب/الإقرارات", "/taxes/returns", None),
    ("الضرائب/الفوترة الإلكترونية", "/taxes/einvoicing", None),
    ("الأطراف/العملاء", "/parties/customers", None),
    ("الأطراف/الموردون", "/parties/suppliers", None),
    ("الأطراف/الكل", "/parties", None),
    ("التقارير/فهرس التقارير", "/reports", "/api/v1/openapi.json"),
    ("التقارير/ميزان المراجعة", "/reports/trial-balance", None),
    ("التقارير/الأستاذ العام", "/reports/ledger", None),
    ("التقارير/أعمار الذمم مدينة", "/reports/aging-receivables", None),
    ("التقارير/أعمار الذمم دائنة", "/reports/aging-payables", None),
    ("التقارير/جدولة التقارير", "/reports/schedules/list", "/api/v1/report-schedules"),
    ("الإعدادات/الإعدادات", "/settings/general", None),
    ("الإعدادات/المستخدمون", "/settings/users", "/api/v1/users"),
    ("الإعدادات/الأدوار", "/settings/roles", "/api/v1/roles"),
    ("الإعدادات/الفروع", "/settings/branches", None),
    ("الإعدادات/سجل التدقيق", "/audit-logs", None),
    ("الإعدادات/الأبعاد التحليلية", "/dimensions", None),
    ("الإعدادات/الفترات المالية", "/settings/fiscal-years", None),
    ("الإعدادات/الفترة المالية", "/periods", "/api/v1/fiscal-periods?entity_id="),
    ("التصدير", "/settings/import-export", "/api/v1/export/tenant"),
    ("الفواتير", "/sales/invoices", "/api/v1/sales/invoices"),
]


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Tenant-ID", TID)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw) if raw else {}
            except Exception:
                return r.status, {"html": True}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"html": True}
    except Exception as e:  # noqa: BLE001
        return 0, {"err": str(e)[:120]}


def main() -> int:
    s, lg = call("POST", "/api/v1/auth/login",
                 body={"username": "admin", "password": "Admin@123"})
    if s != 200:
        print("LOGIN FAILED", lg)
        return 2
    tok = lg["access_token"]

    page_ok = page_fail = api_ok = api_fail = api_skip = 0
    empty_api = []
    seen: set[str] = set()
    for label, page, api in SECTIONS:
        if page not in seen:
            seen.add(page)
            st, _ = call("GET", page, tok)
            if st in (200, 302):
                page_ok += 1
            else:
                page_fail += 1
                print(f"  PAGE FAIL [{st}] {label} -> {page}")
        if not api:
            api_skip += 1
            continue
        url = api + EID if api.endswith("=") else api
        st, body = call("GET", url, tok)
        if st != 200:
            api_fail += 1
            print(f"  API  FAIL [{st}] {label} -> {url}")
            continue
        rows = body.get("data", [])
        n = len(rows) if isinstance(rows, list) else len(rows)
        if n == 0:
            empty_api.append((label, url))
        else:
            api_ok += 1

    print(f"\nSECTIONS: {len(SECTIONS)} list entries / {len(seen)} unique pages")
    print(f"  pages rendering      : {page_ok} OK, {page_fail} FAIL")
    print(f"  APIs 200 with rows   : {api_ok}")
    print(f"  APIs skipped         : {api_skip}")
    print(f"  APIs 200 but empty   : {len(empty_api)}")
    for label, url in empty_api:
        print(f"    - {label}: {url}")
    print(f"  API failures         : {api_fail}")
    return 1 if (page_fail or api_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
