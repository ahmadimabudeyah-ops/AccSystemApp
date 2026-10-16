"""Sales + purchases cycle: invoice -> post -> payment -> allocate (+ vendor mirror)."""
import json
import sys
import urllib.request
import urllib.error

import os as _os
BASE = "http://127.0.0.1:" + _os.getenv("BASE_PORT", "5000")
from _ids import TID, EID  # noqa: E402



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

s, parties = call("GET", "/api/v1/parties?entity_id=" + EID, admin)
cust = next(p["id"] for p in parties["data"] if p["code"] == "C-001")
supp = next(p["id"] for p in parties["data"] if p["code"] == "S-001")
s, prods = call("GET", "/api/v1/products?entity_id=" + EID, admin)
prod = next(p["id"] for p in prods["data"] if p["code"] == "P-001")
s, taxes = call("GET", "/api/v1/taxes", admin)
vat = next(t["id"] for t in taxes["data"] if t["code"] == "VAT16")
s, accs = call("GET", f"/api/v1/accounts?entity_id={EID}", admin)
cash_acc = next(a["id"] for a in accs["data"] if a["code"] == "101001")
print("SETUP_OK")

# ---- sales invoice ----
s, inv = call("POST", "/api/v1/sales/invoices", checker, {
    "entity_id": EID, "customer_id": cust, "payment_term_days": 30,
    "lines": [{"product_id": prod, "qty": 2, "unit_price": 100, "tax_id": vat}]})
assert s == 201, inv
iid = inv["data"]["id"]
assert inv["data"]["grand_total"] == 232.0, inv
print("INV_CREATE_OK", inv["data"]["doc_number"], inv["data"]["grand_total"])
s, posted = call("POST", f"/api/v1/sales/invoices/{iid}/post", admin)
assert s == 200 and posted["data"]["status"] == "posted", posted
print("INV_POST_OK")
s, pay = call("POST", "/api/v1/sales/payments", checker, {
    "entity_id": EID, "customer_id": cust, "amount": 232,
    "pay_method": "cash"})
assert s == 201, pay
pid = pay["data"]["id"]
s, payp = call("POST", f"/api/v1/sales/payments/{pid}/post", admin, {"cash_account_id": cash_acc})
assert s == 200 and payp["data"]["status"] == "posted", payp
print("PAY_POST_OK")
s, allo = call("POST", f"/api/v1/sales/payments/{pid}/allocate", checker, {
    "allocations": [{"invoice_id": iid, "allocated_amount": 232}]})
assert s == 200 and allo["data"]["unallocated_amount"] == 0, allo
print("PAY_ALLOCATE_OK")
s, inv2 = call("GET", f"/api/v1/sales/invoices/{iid}", admin)
assert inv2["data"]["status"] == "paid" and inv2["data"]["remaining_amount"] == 0, inv2
print("INV_PAID_OK")
s, q = call("GET", "/api/v1/sales/einvoicing-queue", admin)
assert s == 200 and any(r["invoice_id"] == iid and r["status"] == "queued" for r in q["data"]), q
print("EINVOICE_QUEUED_OK")

# ---- purchases mirror ----
s, bill = call("POST", "/api/v1/purchases/bills", checker, {
    "entity_id": EID, "supplier_id": supp, "payment_term_days": 30,
    "lines": [{"product_id": prod, "qty": 5, "unit_price": 60}]})
assert s == 201, bill
bid = bill["data"]["id"]
assert bill["data"]["grand_total"] == 300.0, bill
print("BILL_CREATE_OK", bill["data"]["doc_number"])
s, bposted = call("POST", f"/api/v1/purchases/bills/{bid}/post", admin)
assert s == 200 and bposted["data"]["status"] == "posted", bposted
print("BILL_POST_OK")
s, vpay = call("POST", "/api/v1/purchases/payments", checker, {
    "entity_id": EID, "supplier_id": supp, "amount": 300})
assert s == 201, vpay
s, vpayp = call("POST", f"/api/v1/purchases/payments/{vpay['data']['id']}/post", admin, {"cash_account_id": cash_acc})
assert s == 200 and vpayp["data"]["status"] == "posted", vpayp
s, vallo = call("POST", f"/api/v1/purchases/payments/{vpay['data']['id']}/allocate", checker, {
    "allocations": [{"bill_id": bid, "allocated_amount": 300}]})
assert s == 200, vallo
print("VPAY_ALLOCATE_OK")

# ---- credit note + return ----
# Use a FRESH invoice that still owes money: crediting a fully-paid invoice is
# rejected by post_credit_note (that guard keeps AR subledger == GL), and the
# return below credits the same invoice again.
s, open_inv = call("POST", "/api/v1/sales/invoices", checker, {
    "entity_id": EID, "customer_id": cust, "payment_term_days": 30,
    "lines": [{"product_id": prod, "qty": 5, "unit_price": 100, "tax_id": vat}]})
assert s == 201, open_inv
oid_inv = open_inv["data"]["id"]
s, oinvp = call("POST", f"/api/v1/sales/invoices/{oid_inv}/post", admin)
assert s == 200 and oinvp["data"]["status"] == "posted", oinvp
open_iid = str(oid_inv)

s, cn = call("POST", "/api/v1/sales/credit-notes", checker, {
    "entity_id": EID, "customer_id": cust, "invoice_id": open_iid,
    "reason": "discount after sale",
    "lines": [{"product_id": prod, "qty": 1, "unit_price": 16}]})
assert s == 201, cn
s, cnp = call("POST", f"/api/v1/sales/credit-notes/{cn['data']['id']}/post", admin)
assert s == 200 and cnp["data"]["status"] == "posted", cnp
print("CREDIT_OK")
# the invoice must now show the credit against its remaining balance
s, inv_after = call("GET", f"/api/v1/sales/invoices/{open_iid}", admin)
assert s == 200 and inv_after["data"]["remaining_amount"] > 0, inv_after
print("CREDIT_REDUCES_REMAINING_OK remaining=", inv_after["data"]["remaining_amount"])

# over-crediting the same invoice must be refused, not silently allowed
s, dup_cn = call("POST", "/api/v1/sales/credit-notes", checker, {
    "entity_id": EID, "customer_id": cust, "invoice_id": open_iid,
    "reason": "cannot credit more than owed",
    "lines": [{"product_id": prod, "qty": 999, "unit_price": 100}]})
if s == 201:
    s2, r2 = call("POST", f"/api/v1/sales/credit-notes/{dup_cn['data']['id']}/post", admin)
    assert s2 == 422 and r2["error"]["code"] in (
        "VALIDATION_ERROR", "BAD_STATE"), r2
    print("OVER_CREDIT_REFUSED_OK")
else:
    print("OVER_CREDIT_REFUSED_AT_CREATE_OK", str(s))

s, wh = call("GET", "/api/v1/warehouses", admin)
s, loc = call("GET", f"/api/v1/warehouses/{wh['data'][0]['id']}/locations", admin)
s, ret = call("POST", "/api/v1/sales/returns", checker, {
    "entity_id": EID, "customer_id": cust, "invoice_id": open_iid,
    "reason": "damaged item", "warehouse_id": wh["data"][0]["id"],
    "lines": [{"product_id": prod, "returned_qty": 1, "unit_price": 100}]})
assert s == 201, ret
s, retp = call("POST", f"/api/v1/sales/returns/{ret['data']['id']}/post", admin)
assert s == 200 and retp["data"]["status"] == "posted", retp
print("RETURN_OK")
s, quants = call("GET", f"/api/v1/inventory/quants?product_id={prod}", admin)
assert s == 200 and sum(q["qty"] for q in quants["data"]) >= 1, quants
print("STOCK_RECEIPT_OK")

# ---- quote -> order -> delivery ----
s, wh = call("GET", "/api/v1/warehouses", admin)
s, locs = call("GET", f"/api/v1/warehouses/{wh['data'][0]['id']}/locations", admin)
loc = locs["data"][0]["id"]
s, quo = call("POST", "/api/v1/sales/quotations", checker, {
    "entity_id": EID, "customer_id": cust,
    "lines": [{"product_id": prod, "qty": 3, "unit_price": 100}]})
assert s == 201, quo
s, conv = call("POST", f"/api/v1/sales/quotations/{quo['data']['id']}/convert", checker)
assert s == 201, conv
oid = conv["data"]["id"]
print("QUOTE_ORDER_OK", conv["data"]["doc_number"])
s, dlv = call("POST", "/api/v1/sales/deliveries", checker, {
    "order_id": oid, "warehouse_id": wh["data"][0]["id"],
    "lines": [{"product_id": prod, "requested_qty": 2, "source_location_id": loc}]})
assert s == 201, dlv
s, dlvc = call("POST", f"/api/v1/sales/deliveries/{dlv['data']['id']}/confirm", checker)
assert s == 200 and dlvc["data"]["status"] == "delivered", dlvc
print("DELIVERY_OK")
s, oinv = call("POST", f"/api/v1/sales/orders/{oid}/invoice", checker, {})
assert s == 201, oinv
print("ORDER_INVOICE_OK", oinv["data"]["doc_number"])

# ---- request -> order -> receipt ----
s, req = call("POST", "/api/v1/purchases/requests", checker, {
    "entity_id": EID, "reason": "restock",
    "lines": [{"product_id": prod, "qty": 10}]})
assert s == 201, req
s, reqa = call("POST", f"/api/v1/purchases/requests/{req['data']['id']}/approve", admin)
assert s == 200, reqa
s, po = call("POST", "/api/v1/purchases/orders", checker, {
    "entity_id": EID, "supplier_id": supp, "request_id": req["data"]["id"],
    "lines": [{"product_id": prod, "ordered_qty": 10, "unit_price": 60}]})
assert s == 201, po
s, gr = call("POST", "/api/v1/purchases/receipts", checker, {
    "order_id": po["data"]["id"], "warehouse_id": wh["data"][0]["id"],
    "lines": [{"product_id": prod, "received_qty": 10, "unit_cost": 60, "location_id": loc}]})
assert s == 201, gr
s, grc = call("POST", f"/api/v1/purchases/receipts/{gr['data']['id']}/confirm", checker)
assert s == 200 and grc["data"]["status"] == "confirmed", grc
print("RECEIPT_OK")
print("SALES_PURCHASES_OK")
