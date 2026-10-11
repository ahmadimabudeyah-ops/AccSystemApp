"""Debug tax filing in-process."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    db.session.execute(
        text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    from app.models.user import User  # noqa: E402
    from app.models.entity import Entity  # noqa: E402
    from app.models.treasury import Tax  # noqa: E402
    from app.services import ops_service  # noqa: E402
    admin = db.session.query(User).filter_by(email="admin@demo.local").first()
    e = db.session.query(Entity).filter_by(code="MAIN").first()
    tax = db.session.query(Tax).filter_by(code="VAT16").first()
    try:
        r = ops_service.file_tax_return(tenant_id=admin.tenant_id, entity_id=e.id,
                                        tax_id=tax.id, period_code="2026-01",
                                        actor_id=admin.id)
        print("FILED", r.tax_due)
    except Exception:
        import traceback  # noqa: E402
        traceback.print_exc()
