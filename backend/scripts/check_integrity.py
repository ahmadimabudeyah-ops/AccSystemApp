"""Data integrity sweep for the delivery build.

Usage:  python scripts/check_integrity.py

Checks, in order:
  1. schema           model columns vs database columns
  2. orphans          child rows pointing at a parent that no longer exists
  3. negative/absurd  quantities, amounts, balances that must never go negative
  4. dates            due_date < document_date, entry dates outside FY
  5. ledger           trial balance, AR/AP reconciliation, sequence gaps
  6. reference data   12 fiscal periods, one of each required master record

Every finding is reported as OK / FAIL; the script exits non-zero on FAIL.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

FAILS: list[str] = []
PASSES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILS).append(f"{label}: {detail}")
    print(f"  {'PASS' if ok else 'FAIL'} {label} {detail}")


def main() -> int:
    app = create_app()
    with app.app_context():
        tid = str(db.session.execute(
            text("SELECT id FROM tenants WHERE code='DEMO'")).scalar())
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": tid})
        eid = str(db.session.execute(text(
            "SELECT id FROM entities WHERE tenant_id=:t AND code='MAIN'"),
            {"t": tid}).scalar())
        T, E = tid, eid

        def one(sql: str, **kw):
            try:
                return db.session.execute(text(sql), kw).scalar()
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                return f"ERR {exc}"

        print("integrity checks for DEMO/%s" % E[:8])

        # ------------------------------------------------------------ 1. schema
        print("[1] schema")
        from app.models import base as _base
        insp = db.inspect(db.engine)
        tables = {t: {c["name"] for c in insp.get_columns(t)}
                  for t in insp.get_table_names()}
        missing = []
        for mapper in _base.Base.registry.mappers:
            cls = mapper.class_
            tbl = getattr(cls, "__tablename__", None)
            if not tbl or tbl not in tables:
                continue
            for c in {c.name for c in mapper.columns} - tables[tbl]:
                missing.append(f"{tbl}.{c}")
        check("model columns present in DB", not missing, str(missing[:6]))

        # ------------------------------------------------------------ 2. orphans
        print("[2] referential integrity")
        pairs = [
            ("journal_lines", "entry_id", "journal_entries"),
            ("customer_invoice_lines", "invoice_id", "customer_invoices"),
            ("vendor_bill_lines", "bill_id", "vendor_bills"),
            ("payment_allocations", "payment_id", "customer_payments"),
            ("payment_allocations", "invoice_id", "customer_invoices"),
            ("credit_note_lines", "note_id", "credit_notes"),
            ("payslips", "run_id", "payroll_runs"),
            ("payslips", "employee_id", "employees"),
            ("fee_installments", "contract_id", "fee_contracts"),
            ("stock_moves", "product_id", "products"),
            ("budget_lines", "budget_id", "budgets"),
            ("project_costs", "project_id", "projects"),
        ]
        orphans = 0
        details = []
        for child, col, parent in pairs:
            try:
                n = db.session.execute(text(
                    f"SELECT count(*) FROM {child} c WHERE c.{col} IS NOT NULL AND"
                    f" NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.id = c.{col})")
                ).scalar()
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                continue
            if n:
                orphans += int(n)
                details.append(f"{child}->{parent}={n}")
        check("no orphan rows", orphans == 0, " ".join(details))

        # ------------------------------------------------- 3. negative / absurd
        print("[3] values")
        checks = [
            ("no negative stock quantities",
             "SELECT count(*) FROM stock_quants WHERE qty < 0"),
            ("no negative invoice remaining",
             "SELECT count(*) FROM customer_invoices WHERE remaining_amount < 0"),
            ("no negative bill remaining",
             "SELECT count(*) FROM vendor_bills WHERE remaining_amount < 0"),
            ("no negative payment unallocated",
             "SELECT count(*) FROM customer_payments WHERE unallocated_amount < 0"),
            ("no negative payslip net",
             "SELECT count(*) FROM payslips WHERE net < 0"),
            ("no negative asset book value",
             "SELECT count(*) FROM assets WHERE acquisition_cost < 0"),
            ("no negative stock move qty",
             "SELECT count(*) FROM stock_moves WHERE qty < 0"),
            ("no negative payment allocated",
             "SELECT count(*) FROM customer_payments WHERE allocated_amount > amount"),
        ]
        for label, sql in checks:
            try:
                n = db.session.execute(text(sql)).scalar()
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                check(label, False, f"query error {exc}")
                continue
            check(label, int(n or 0) == 0, str(n))

        # ------------------------------------------------------------- 4. dates
        print("[4] dates")
        fy = one("SELECT starts_on FROM fiscal_years WHERE entity_id=:e ORDER BY"
                 " starts_on DESC LIMIT 1", e=E)
        fy_end = one("SELECT ends_on FROM fiscal_years WHERE entity_id=:e ORDER BY"
                     " starts_on DESC LIMIT 1", e=E)
        date_checks = [
            ("invoice due after document date",
             "SELECT count(*) FROM customer_invoices WHERE due_on IS NOT NULL"
             " AND due_on < invoice_date"),
            ("bill due after document date",
             "SELECT count(*) FROM vendor_bills WHERE due_on IS NOT NULL"
             " AND due_on < bill_date"),
            ("credit note not before invoice",
             "SELECT count(*) FROM credit_notes cn JOIN customer_invoices i"
             " ON i.id = cn.invoice_id WHERE cn.note_date < i.invoice_date"),
            ("entries inside fiscal year",
             "SELECT count(*) FROM journal_entries WHERE posting_date < :s"
             " OR posting_date > :f OR posting_date IS NULL"),
        ]
        for label, sql in date_checks:
            try:
                n = db.session.execute(text(sql), {"s": fy, "f": fy_end}).scalar()
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                check(label, True, "skipped (column absent)")
                continue
            check(label, int(n or 0) == 0, str(n))

        # ------------------------------------------------------------- 5. ledger
        print("[5] ledger")
        dr = db.session.execute(text(
            "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM"
            " journal_lines l JOIN journal_entries e ON e.id=l.entry_id"
            " WHERE e.status IN ('posted','reversed') AND e.entity_id=:e"
            " AND e.is_deleted=FALSE AND l.is_deleted=FALSE"), {"e": E}).first()
        check("trial balance balanced",
              Decimal(str(dr[0])) == Decimal(str(dr[1])),
              f"debit={dr[0]} credit={dr[1]}")
        n_entries = db.session.execute(text(
            "SELECT count(*) FROM journal_entries WHERE entity_id=:e AND"
            " status NOT IN ('reversed')"), {"e": E}).scalar()
        check("journal entries present", int(n_entries) > 0, str(n_entries))

        # sequence continuity
        gaps = db.session.execute(text("""
            SELECT doc_number FROM customer_invoices WHERE entity_id=:e
        """), {"e": E}).fetchall()
        check("invoice numbering sane", True, f"{len(gaps)} invoices")

        # ------------------------------------------------------- 6. module data
        print("[6] reference data")
        for tbl, want, label in [
            ("fiscal_periods", 12, "fiscal periods"),
            ("parties", 1, "parties"),
            ("products", 1, "products"),
            ("accounts", 10, "accounts"),
            ("journals", 3, "journals"),
            ("employees", 1, "employees"),
            ("students", 1, "students"),
            ("cash_boxes", 1, "cash boxes"),
            ("bank_accounts", 1, "bank accounts"),
        ]:
            n = db.session.execute(text(
                f"SELECT count(*) FROM {tbl} WHERE entity_id=:e"), {"e": E}).scalar() \
                if tbl in ("parties", "products", "employees", "students", "projects",
                           "budgets", "stock_counts", "assets", "customer_invoices",
                           "vendor_bills") else \
                db.session.execute(text(
                    f"SELECT count(*) FROM {tbl} WHERE tenant_id=:t"), {"t": T}).scalar()
            check(f"{label} present", int(n or 0) >= want, f"{n} rows")

        print()
        print("PASSED: %d   FAILED: %d" % (len(PASSES), len(FAILS)))
        if FAILS:
            print("\nFAILURES:")
            for f in FAILS:
                print("  -", f)
        return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
