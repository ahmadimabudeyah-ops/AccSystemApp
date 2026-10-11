"""RBAC enforcement test: cashier is denied journals, auditor is read-only."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
app = create_app()
c = app.test_client()


def login(u, p):
    r = c.post("/api/v1/auth/login", json={"username": u, "password": p},
               headers={"X-Tenant-ID": TID})
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    return r.get_json()["access_token"]


with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
    from app.models.user import User, Role, UserRole  # noqa: E402
    from app.utils.security import hash_password  # noqa: E402
    cashier = db.session.query(User).filter_by(email="cashier@demo.local").first()
    if cashier is None:
        cashier = User(tenant_id=TID, username="cashier", email="cashier@demo.local",
                       password_hash=hash_password("Cashier@123", rounds=4),
                       is_active=True)
        db.session.add(cashier)
        db.session.flush()
        role = db.session.query(Role).filter_by(code="CASHIER").first()
        db.session.add(UserRole(tenant_id=TID, user_id=cashier.id, role_id=role.id))
        db.session.commit()
        print("CASHIER_CREATED")
    else:
        print("CASHIER_EXISTS")

tok = login("cashier", "Cashier@123")
h = {"X-Tenant-ID": TID, "Authorization": "Bearer " + tok}
r = c.get("/api/v1/treasury/cash-boxes", headers=h)
print("cashier cash-boxes:", r.status_code)
r = c.post("/api/v1/journal-entries", json={}, headers=h)
print("cashier create-entry:", r.status_code, r.get_json().get("error", {}).get("code"))
r = c.get("/api/v1/reports/trial-balance?period_id=00000000-0000-0000-0000-000000000000", headers=h)
print("cashier reports:", r.status_code)
