"""Debug cash-flow SQL in-process."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    db.session.execute(
        text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    try:
        rows = db.session.execute(text(
            "SELECT date_trunc('month', e.posting_date)::date AS m, "
            "SUM(CASE WHEN l.debit > 0 THEN l.debit ELSE -l.credit END)::float AS net "
            "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
            "JOIN accounts a ON a.id = l.account_id "
            "WHERE e.entity_id = :en AND e.status = 'posted' AND e.is_deleted = FALSE "
            "AND l.is_deleted = FALSE AND (a.code LIKE '101%' OR a.code LIKE '102%') "
            "GROUP BY 1 ORDER BY 1"),
            {"en": "f50db4a1-9381-400d-954b-79c515667f74"}).all()
        print("ROWS:", rows)
    except Exception:
        import traceback  # noqa: E402
        traceback.print_exc()
