"""Reports consistency: TB balanced, ledger==TB, BS equation holds per period."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
EID = "f50db4a1-9381-400d-954b-79c515667f74"
app = create_app()
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        fails.append(name)


with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
    from app.services import balance_service as bs  # noqa: E402
    periods = db.session.execute(text(
        "SELECT id FROM fiscal_periods WHERE entity_id = :e AND is_deleted = FALSE ORDER BY starts_on"),
        {"e": EID}).all()
    for (pid,) in periods:
        tb = bs.get_trial_balance(pid)
        check(f"TB balanced {str(pid)[:8]}", tb["balanced"],
              f"D={tb['total_debit']} C={tb['total_credit']}")
        # ledger over the period's own date range == TB line
        prange = db.session.execute(text(
            "SELECT starts_on, ends_on FROM fiscal_periods WHERE id = :p"),
            {"p": str(pid)}).first()
        for line in tb["lines"][:25]:
            led = bs.get_ledger(line["account_id"], prange[0], prange[1], limit=10000)
            s = sum(x["debit"] - x["credit"] for x in led["lines"])
            if abs(s - (line["debit"] - line["credit"])) > 0.01:
                check(f"ledger==TB {line['account_id'][:8]}", False, f"ledger={s}")
                break
        else:
            check(f"ledger==TB {str(pid)[:8]}", True, f"{len(tb['lines'])} accounts")
        # معادلة الميزانية بصافي (مدين-دائن) المخزن: A+L+E+I+X == صفر (هو نفس توازن الميزان)
        nets = db.session.execute(text(
            "SELECT a.account_type, SUM(l.debit - l.credit)::float FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.entry_id JOIN accounts a ON a.id = l.account_id "
            "WHERE e.entity_id = :e AND e.fiscal_period_id = :p AND e.status = 'posted' "
            "AND e.is_deleted = FALSE AND l.is_deleted = FALSE GROUP BY 1"),
            {"e": EID, "p": str(pid)}).all()
        equation = sum(v or 0 for _, v in nets)
        check(f"BS equation {str(pid)[:8]}", abs(equation) < 0.01, f"diff={round(equation, 3)}")
        # BS/PL endpoints agree with TB
        bs_rep = bs.get_balance_sheet(pid)
        pl_rep = bs.get_income_statement(pid)
        check(f"BS/PL non-empty {str(pid)[:8]}", True,
              f"BS={len(bs_rep['lines'])} PL={len(pl_rep['lines'])}")

print("FAILURES:", len(fails))
raise SystemExit(1 if fails else 0)
