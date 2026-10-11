"""Debug reversal in-process."""
import sys
import uuid
from datetime import date

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    db.session.execute(
        text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    from app.models.user import User  # noqa: E402
    from app.services import reversal_service  # noqa: E402
    admin = db.session.query(User).filter_by(email="admin@demo.local").first()
    from app.models.journal import JournalEntry  # noqa: E402
    e = (db.session.query(JournalEntry)
         .filter_by(status="posted", is_deleted=False)
         .order_by(JournalEntry.created_at.desc()).first())
    print("TARGET", e.id, e.status)
    try:
        rev = reversal_service.reverse_full(
            e.id, reason="debug reversal", reversal_date=date(2026, 1, 9),
            actor_id=admin.id, event_key="dbg.rev." + uuid.uuid4().hex[:8])
        print("REVERSED", rev.id, rev.status, rev.official_number)
    except Exception:
        import traceback  # noqa: E402
        traceback.print_exc()
