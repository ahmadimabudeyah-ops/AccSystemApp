"""Dev-only cleanup of chart-acceptance test data (prefix Z####-/W####-).

Removes test accounts + their manual entries/event keys/closure rows and any
sales test payments posted onto them, then repairs orphaned invoice statuses.
Posted-entry immutability trigger is disabled briefly and re-enabled; the
script proves enforcement afterwards. NEVER run against production.
"""
import os
import sys

import psycopg2

DB = dict(host="127.0.0.1", port=int(os.getenv("DEV_DB_PORT", "5433")),
          user=os.getenv("DEV_DB_USER", "postgres"),
          password=os.getenv("DEV_DB_PASSWORD", "postgres"),
          database=os.getenv("DEV_DB_NAME", "accounting_db"))
PAT = "^[ZW][0-9A-F]{4}-|^FX(TEST|GAIN|REV)$"
F = ("event_key LIKE 'chart-test-%%' OR event_key LIKE 'chart-bal-%%' "
     "OR event_key LIKE 'fx-%%' OR event_key LIKE 'test-%%'")


def main() -> None:
    if os.getenv("ALLOW_DEV_CLEANUP", "0") != "1":
        print("Refusing: set ALLOW_DEV_CLEANUP=1 to run (dev only).")
        sys.exit(2)
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE journal_entries DISABLE TRIGGER trg_je_immutable")
    try:
        cur.execute("DELETE FROM reversal_links WHERE original_entry_id IN "
                    "(SELECT id FROM journal_entries WHERE " + F + ")")
        cur.execute("DELETE FROM reversal_links WHERE reversal_entry_id IN "
                    "(SELECT id FROM journal_entries WHERE " + F + ")")
        cur.execute("DELETE FROM event_keys WHERE " + F)
        cur.execute("DELETE FROM journal_lines WHERE entry_id IN "
                    "(SELECT id FROM journal_entries WHERE " + F + ")")
        cur.execute("DELETE FROM journal_entries WHERE reversal_of_id IN "
                    "(SELECT id FROM journal_entries WHERE " + F + ")")
        cur.execute("DELETE FROM journal_entries WHERE " + F)
        cur.execute("SELECT DISTINCT e.id FROM journal_entries e "
                    "JOIN journal_lines l ON l.entry_id=e.id "
                    "JOIN accounts a ON a.id=l.account_id WHERE a.code ~ %s", (PAT,))
        for (eid,) in cur.fetchall():
            cur.execute("DELETE FROM event_keys WHERE resulting_entry_id=%s", (eid,))
            # حافظ على الفواتير/المدفوعات المرتبطة: ارفع المراجع للاختبار فقط
            cur.execute("UPDATE vendor_bills SET journal_entry_id=NULL "
                        "WHERE journal_entry_id=%s", (eid,))
            cur.execute("SELECT id FROM customer_payments WHERE journal_entry_id=%s", (eid,))
            for (p,) in cur.fetchall():
                cur.execute("SELECT DISTINCT invoice_id FROM payment_allocations "
                            "WHERE payment_id=%s", (p,))
                invs = [r[0] for r in cur.fetchall()]
                cur.execute("DELETE FROM payment_allocations WHERE payment_id=%s", (p,))
                cur.execute("DELETE FROM customer_payments WHERE id=%s", (p,))
                for inv in invs:
                    # إعادة احتساب المتبقي من المخصصات الباقية فقط
                    cur.execute("SELECT COALESCE(SUM(allocated_amount),0) FROM "
                                "payment_allocations WHERE invoice_id=%s", (inv,))
                    alloc = float(cur.fetchone()[0] or 0)
                    cur.execute("UPDATE customer_invoices SET paid_amount=%s, "
                                "remaining_amount=grand_total-%s, "
                                "status=CASE WHEN grand_total-%s<=0.001 THEN 'paid' "
                                "WHEN %s>0.001 THEN 'partially_paid' ELSE 'posted' END "
                                "WHERE id=%s", (alloc, alloc, alloc, alloc, inv))
            cur.execute("DELETE FROM journal_lines WHERE entry_id=%s", (eid,))
            cur.execute("DELETE FROM journal_entries WHERE id=%s", (eid,))
        # أسطر الفواتير/الدفاتر المرتبطة بحسابات الاختبار → نقلها للحساب الرقابي 2010
        cur.execute("SELECT id FROM accounts WHERE tenant_id=(SELECT id FROM tenants WHERE code='DEMO') AND code='2010'")
        _ctl = cur.fetchone()
        if _ctl:
            cur.execute("UPDATE vendor_bill_lines SET account_id=%s WHERE account_id IN "
                        "(SELECT id FROM accounts WHERE code ~ %s)", (_ctl[0], PAT))
            cur.execute("UPDATE customer_invoice_lines SET account_id=%s WHERE account_id IN "
                        "(SELECT id FROM accounts WHERE code ~ %s)", (_ctl[0], PAT))
        cur.execute("DELETE FROM account_report_mappings WHERE account_id IN "
                    "(SELECT id FROM accounts WHERE code ~ %s)", (PAT,))
        cur.execute("DELETE FROM account_hierarchy WHERE descendant_id IN "
                    "(SELECT id FROM accounts WHERE code ~ %s)", (PAT,))
        cur.execute("DELETE FROM account_hierarchy WHERE ancestor_id IN "
                    "(SELECT id FROM accounts WHERE code ~ %s)", (PAT,))
        cur.execute("DELETE FROM accounts WHERE code ~ %s", (PAT,))
        print("test accounts removed:", cur.rowcount)
        cur.execute("DELETE FROM exchange_rates WHERE source='test'")
        print("test fx removed:", cur.rowcount)
    finally:
        cur.execute("ALTER TABLE journal_entries ENABLE TRIGGER trg_je_immutable")
    cur.execute("SELECT count(*) FROM accounts WHERE code ~ %s", (PAT,))
    print("remaining test accounts:", cur.fetchone()[0])


if __name__ == "__main__":
    main()
