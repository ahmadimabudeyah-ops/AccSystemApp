"""Repair: invoices whose remaining_amount went negative.

Cause: an earlier build of credit_service.post_credit_note applied the credit
without checking it against the invoice's outstanding balance, so posting two
credit notes onto an already-settled invoice drove remaining_amount negative
(the current code raises ValidationError instead).

This script recomputes every invoice from its own components:
    remaining = grand_total - sum(payment allocations) - sum(credit notes)
and rewrites paid_amount / status.  It refuses to "fix" anything by silently
capping, so a real over-credit is reported rather than papered over.

Usage:  python scripts/repair_invoice_balances.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

DRY = "--dry-run" in sys.argv


def main() -> int:
    app = create_app()
    with app.app_context():
        tid = str(db.session.execute(
            text("SELECT id FROM tenants WHERE code='DEMO'")).scalar())
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": tid})

        rows = db.session.execute(text("""
            SELECT i.id, i.doc_number, i.status,
                   i.grand_total::numeric,
                   COALESCE((SELECT SUM(pa.allocated_amount) FROM payment_allocations pa
                             WHERE pa.invoice_id = i.id), 0)::numeric AS allocated,
                   COALESCE((SELECT SUM(cn.grand_total) FROM credit_notes cn
                             WHERE cn.invoice_id = i.id AND cn.status = 'posted'
                             AND cn.is_deleted = FALSE), 0)::numeric AS credited,
                   i.remaining_amount::numeric AS stored_remaining,
                   i.paid_amount::numeric AS stored_paid
            FROM customer_invoices i
            WHERE i.is_deleted = FALSE
            ORDER BY i.doc_number
        """)).fetchall()

        fixed = 0
        for inv_id, doc, status, grand, allocated, credited, rem, paid in rows:
            correct_remaining = Decimal(str(grand)) - Decimal(str(allocated)) \
                - Decimal(str(credited))
            correct_paid = Decimal(str(allocated)) + Decimal(str(credited))
            if correct_remaining == Decimal(str(rem)) \
                    and correct_paid == Decimal(str(paid)):
                continue
            over = correct_remaining < 0
            print(f"{doc}: remaining {rem} -> {correct_remaining}, "
                  f"paid {paid} -> {correct_paid}"
                  + ("  *** OVER-CREDITED ***" if over else ""))
            if DRY:
                continue
            # A negative remainder is real data corruption, so flag it loudly
            # and set the clamped value; the over-credit must be resolved with a
            # debit note by the accountant, not hidden.
            new_rem = max(Decimal("0"), correct_remaining)
            new_status = "paid" if new_rem <= Decimal("0.001") else (
                "partially_paid" if correct_paid > 0 else "posted")
            db.session.execute(text(
                "UPDATE customer_invoices SET remaining_amount = :r,"
                " paid_amount = :p, status = :s WHERE id = :i"),
                {"r": float(new_rem), "p": float(correct_paid), "s": new_status,
                 "i": str(inv_id)})
            fixed += 1

        if not DRY:
            db.session.commit()
        print(f"REPAIR{' DRY-RUN' if DRY else ''}: {fixed} invoice(s) corrected "
              f"out of {len(rows)}")
        over = [r[1] for r in rows
                if Decimal(str(r[3])) - Decimal(str(r[4]))
                - Decimal(str(r[5])) < 0]
        if over:
            print("OVER-CREDITED (needs a debit note): "
                  + ", ".join(over))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
