"""Debug: post entry in-process to surface the traceback."""
import sys
import uuid

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    db.session.execute(
        text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    from app.models.user import User  # noqa: E402
    from app.services import posting_service  # noqa: E402
    admin = db.session.query(User).filter_by(email="admin@demo.local").first()
    try:
        r = posting_service.post_entry(
            uuid.UUID("c232a174-4686-4cc5-8530-ecf1b15c852f"), admin.id)
        print("POSTED", r.official_number, r.status)
    except Exception as ex:
        import traceback  # noqa: E402
        traceback.print_exc()
