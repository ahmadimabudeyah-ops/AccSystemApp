"""Deep accounting integrity audit: COA, docs<->entries, allocations, reports consistency."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

from _ids import TID, EID  # noqa: E402

app = create_app()
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        fails.append(name)


with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
    q = lambda sql, **p: db.session.execute(text(sql), {"t": TID, **p}).all()
    one = lambda sql, **p: db.session.execute(text(sql), {"t": str(TID), **p}).scalar()

    # ---- 1. chart of accounts ----
    roots = {r[0]: r[1] for r in q(
        "SELECT code, account_type FROM accounts WHERE tenant_id = :t AND entity_id = :e "
        "AND parent_id IS NULL AND is_deleted = FALSE", e=EID)}
    check("COA 5 roots", set(roots) == {"1", "2", "3", "4", "5"}, str(sorted(roots)))
    must = {"101001": "asset", "102001": "asset", "1210": "asset", "1310": "asset",
            "1519": "contra_asset", "2010": "liability", "2140": "liability",
            "2150": "liability", "2151": "liability", "2160": "liability",
            "3010": "equity", "4010": "income", "4020": "income", "4090": "contra_income",
            "4095": "income", "5010": "expense", "5110": "expense", "5111": "expense",
            "5130": "expense"}
    rows = {r[0]: r[1] for r in q(
        "SELECT code, account_type FROM accounts WHERE tenant_id = :t AND entity_id = :e "
        "AND is_deleted = FALSE", e=EID)}
    missing = [c for c in must if rows.get(c) != must[c]]
    check("COA key accounts+types", not missing, str(missing))
    n_postable = one("SELECT count(*) FROM accounts WHERE tenant_id = :t AND entity_id = :e "
                     "AND is_postable AND is_deleted = FALSE", e=EID)
    check("COA postable leaves", n_postable >= 25, str(n_postable))
    orphans = one("SELECT count(*) FROM accounts a WHERE a.tenant_id = :t AND a.parent_id IS NOT NULL "
                  "AND NOT EXISTS (SELECT 1 FROM accounts p WHERE p.id = a.parent_id)", e=EID)
    check("COA no orphan parents", orphans == 0, str(orphans))

    # ---- 2. every posted business doc has a POSTED entry ----
    for tbl, label in [("customer_invoices", "AR"), ("vendor_bills", "AP"),
                       ("customer_payments", "AR-pay"), ("vendor_payments", "AP-pay"),
                       ("fee_contracts", "EDU"), ("payroll_runs", "PAY")]:
        bad = db.session.execute(text(
            f"SELECT count(*) FROM {tbl} d LEFT JOIN journal_entries e ON e.id = d.journal_entry_id "
            f"WHERE d.tenant_id = :t AND d.status = 'posted' "
            f"AND (d.journal_entry_id IS NULL OR e.status <> 'posted' OR e.is_deleted)"), {"t": TID}).scalar()
        check(f"docs->posted entries [{label}]", bad == 0, str(bad))
    posted_wo_doc = db.session.execute(text(
        "SELECT count(*) FROM journal_entries e WHERE e.tenant_id = :t AND e.status = 'posted' "
        "AND e.entry_type = 'source' AND e.source_document_id IS NULL"), {"t": TID}).scalar()
    check("no sourceless source-entries", posted_wo_doc == 0, str(posted_wo_doc))

    # ---- 3. invoice arithmetic ----
    bad_inv = db.session.execute(text(
        "SELECT i.doc_number FROM customer_invoices i WHERE i.tenant_id = :t AND i.is_deleted = FALSE "
        "AND (SELECT COALESCE(SUM(line_total),0) FROM customer_invoice_lines l "
        "     WHERE l.invoice_id = i.id AND l.is_deleted = FALSE) <> i.subtotal + i.tax_total "
        "OR abs((i.grand_total - i.paid_amount) - i.remaining_amount) > 0.001"), {"t": TID}).all()
    check("invoice lines==totals && remainder", not bad_inv, str([r[0] for r in bad_inv][:3]))
    bad_tax = db.session.execute(text(
        "SELECT i.doc_number FROM customer_invoices i WHERE i.tenant_id = :t AND i.is_deleted = FALSE "
        "AND (SELECT COALESCE(SUM(tax_amount),0) FROM customer_invoice_taxes t "
        "     WHERE t.invoice_id = i.id AND t.is_deleted = FALSE) <> i.tax_total"), {"t": TID}).all()
    check("invoice taxes roll up", not bad_tax, str([r[0] for r in bad_tax][:3]))
    over = db.session.execute(text(
        "SELECT doc_number FROM customer_invoices WHERE tenant_id = :t AND is_deleted = FALSE "
        "AND paid_amount - grand_total > 0.001"), {"t": TID}).all()
    check("no overpaid invoices", not over, str([r[0] for r in over][:3]))
    alloc = db.session.execute(text(
        "SELECT p.doc_number FROM customer_payments p WHERE p.tenant_id = :t AND p.is_deleted = FALSE "
        "AND (SELECT COALESCE(SUM(allocated_amount),0) FROM payment_allocations a "
        "     WHERE a.payment_id = p.id AND a.is_deleted = FALSE) <> p.allocated_amount"),
        {"t": TID}).all()
    check("allocations roll up to payments", not alloc, str([r[0] for r in alloc][:3]))

    # ---- 4. sequences unique ----
    dup = db.session.execute(text(
        "SELECT official_number, count(*) FROM journal_entries WHERE tenant_id = :t "
        "AND official_number IS NOT NULL GROUP BY 1 HAVING count(*) > 1"), {"t": TID}).all()
    check("official numbers unique", not dup, str(dup[:2]))

    # ---- 5. posted only in open periods + balanced ----
    closed = db.session.execute(text(
        "SELECT count(*) FROM journal_entries e JOIN fiscal_periods p ON p.id = e.fiscal_period_id "
        "WHERE e.tenant_id = :t AND e.status = 'posted' AND p.status IN ('soft_closed','hard_closed')"),
        {"t": TID}).scalar()
    check("no postings in closed periods", closed == 0, str(closed))
    unbal = db.session.execute(text(
        "SELECT e.id FROM journal_entries e WHERE e.tenant_id = :t AND e.status = 'posted' "
        "AND (SELECT COALESCE(SUM(debit),0) FROM journal_lines l WHERE l.entry_id = e.id AND l.is_deleted = FALSE) "
        "<> (SELECT COALESCE(SUM(credit),0) FROM journal_lines l WHERE l.entry_id = e.id AND l.is_deleted = FALSE)"),
        {"t": TID}).all()
    check("all posted entries balanced", not unbal, str(len(unbal)))

print("FAILURES:", len(fails))
raise SystemExit(1 if fails else 0)
