"""Repair: post draft entries of already-posted payroll runs (pre-fix artifacts)."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
app = create_app()
with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
    from app.models.user import User  # noqa: E402
    from app.models.hr import PayrollRun  # noqa: E402
    from app.services import posting_service  # noqa: E402
    admin = db.session.query(User).filter_by(email="admin@demo.local").first()
    runs = db.session.query(PayrollRun).filter_by(status="posted").all()
    fixed = 0
    for r in runs:
        e = db.session.get(posting_service.JournalEntry, r.journal_entry_id) if r.journal_entry_id else None
        from app.models.journal import JournalEntry
        e = db.session.get(JournalEntry, r.journal_entry_id) if r.journal_entry_id else None
        if e is not None and e.status == "draft":
            posting_service.post_entry(e.id, admin.id)
            fixed += 1
    print("REPAIRED:", fixed)
