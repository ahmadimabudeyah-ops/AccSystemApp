"""Repair: posted credit notes never reduced the linked invoice's remaining amount.

Root cause: services/credit_service.post_credit_note posted the GL entry but did
not update customer_invoices.remaining_amount, so the AR GL balance and the
invoice subledger diverged (visible in /api/v1/reports/ar-ap-reconciliation).

This script re-applies every *posted* credit note that still has an invoice
linked to it, exactly the way services/credit_service now does it.

Usage:  python scripts/repair_credit_notes.py [--dry-run]
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.sales import CreditNote, CustomerInvoice  # noqa: E402

DRY = "--dry-run" in sys.argv


def main() -> int:
    app = create_app()
    with app.app_context():
        trow = db.session.execute(text("SELECT id FROM tenants WHERE code='DEMO'")).first()
        if not trow:
            print("no tenant")
            return 1
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(trow[0])})

        notes = db.session.query(CreditNote).filter_by(
            status="posted", is_deleted=False).all()
        fixed = 0
        for n in notes:
            if not n.invoice_id:
                continue
            inv = db.session.get(CustomerInvoice, n.invoice_id, with_for_update=True)
            if inv is None or inv.is_deleted:
                continue
            credit = Decimal(str(n.grand_total or 0))
            if credit <= 0:
                continue
            new_rem = Decimal(str(inv.remaining_amount)) - credit
            if new_rem < 0:
                new_rem = Decimal("0")
            print(f"{n.doc_number} -> {inv.doc_number}: remaining "
                  f"{inv.remaining_amount} -> {new_rem} (credit {credit})")
            if DRY:
                continue
            inv.paid_amount = float(Decimal(str(inv.paid_amount)) + credit)
            inv.remaining_amount = float(new_rem)
            inv.status = "paid" if new_rem <= Decimal("0.001") else "partially_paid"
            fixed += 1
        if not DRY:
            db.session.commit()
        print(f"REPAIR{' DRY-RUN' if DRY else ''}: {fixed} invoice(s) updated "
              f"out of {len(notes)} posted credit note(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
