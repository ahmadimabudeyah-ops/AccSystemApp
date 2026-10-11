"""Create checker user (second approver) for the demo cycle."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, Role, UserRole  # noqa: E402
from app.utils.security import hash_password  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    t = db.session.query(Tenant).filter_by(code=os.getenv("TENANT_CODE", "DEMO")).first()
    assert t
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    u = db.session.query(User).filter_by(tenant_id=t.id, email="checker@demo.local").first()
    if u is None:
        u = User(tenant_id=t.id, username="checker", email="checker@demo.local",
                 password_hash=hash_password("Checker@123", rounds=4))
        db.session.add(u)
        db.session.flush()
        u.created_by = u.id
        u.updated_by = u.id
        role = db.session.query(Role).filter_by(tenant_id=t.id, code="ACCOUNTANT").first()
        db.session.add(UserRole(tenant_id=t.id, user_id=u.id, role_id=role.id,
                                created_by=u.id, updated_by=u.id))
        db.session.commit()
    print(f"CHECKER_OK id={u.id}")
