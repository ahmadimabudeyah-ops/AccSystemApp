"""RBAC coverage check: MATRIX codes vs catalog, API perms vs catalog, role details."""
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402
import importlib.util

spec = importlib.util.spec_from_file_location("_m", "scripts/seed_rbac.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TID = "b39787b5-52fb-4fb0-b41f-98b90b5853d6"
app = create_app()
with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": TID})
    from app.models.user import Permission, Role, RolePermission  # noqa: E402
    catalog = {p.code for p in db.session.query(Permission).all()}
    print("CATALOG:", len(catalog))
    for role, want in m.MATRIX.items():
        want = set(catalog) if want == ["*"] else set(want)
        missing = sorted(want - catalog)
        if missing:
            print("MATRIX GAP", role, missing)
    import re
    import glob
    used = set()
    for p in glob.glob("app/api/v1/*.py"):
        for mm in re.finditer(r'_deny\("([a-z._*]+)"\)', open(p, encoding="utf-8").read()):
            used.add(mm.group(1))
    print("API_PERMS_MISSING:", sorted(used - catalog) or "none")
    for r in db.session.query(Role).filter_by(is_deleted=False).order_by(Role.code).all():
        n = db.session.query(RolePermission).filter_by(role_id=r.id).count()
        print(f"ROLE {r.code:20} grants={n}")
