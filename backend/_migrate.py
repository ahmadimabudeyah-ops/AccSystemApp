from app import create_app
from app.extensions import db
from sqlalchemy import text
app = create_app()
with app.app_context():
    db.session.execute(text("SET app.current_tenant_id = :t"), {
        "t": str(db.session.execute(text("SELECT id FROM tenants LIMIT 1")).scalar())})
    from app.models.entity import Entity
    e = db.session.query(Entity).first()

    # 1. Fix 2151/2160: move under Liabilities (code '2')
    liab = db.session.execute(text(
        "SELECT id FROM accounts WHERE entity_id = :e AND code = '2' AND is_deleted = FALSE"
    ), {"e": str(e.id)}).scalar()
    if liab:
        for code in ["2151", "2160"]:
            r = db.session.execute(text(
                "UPDATE accounts SET parent_id = :p, level = 2, "
                "hierarchy_role = 'detail', is_leaf = TRUE "
                "WHERE entity_id = :e AND code = :c AND is_deleted = FALSE AND parent_id IS NULL"
            ), {"p": str(liab), "e": str(e.id), "c": code})
            print(f"  {code}: {r.rowcount} row(s) updated")
    else:
        print("  liability root not found")

    # 2. hierarchy_role for unclassified postable children
    r = db.session.execute(text(
        "UPDATE accounts SET hierarchy_role = 'detail' "
        "WHERE entity_id = :e AND is_deleted = FALSE AND hierarchy_role IS NULL "
        "AND is_postable = TRUE AND parent_id IS NOT NULL"
    ), {"e": str(e.id)})
    print(f"  hierarchy_role: {r.rowcount} rows")

    # 3. control_type for AR/AP/inventory
    for code, ctl in [("1210", "receivable"), ("2010", "payable"), ("1310", "inventory")]:
        r = db.session.execute(text(
            "UPDATE accounts SET control_type = :ctl "
            "WHERE entity_id = :e AND code = :c AND is_deleted = FALSE"
        ), {"e": str(e.id), "c": code, "ctl": ctl})
        print(f"  {code} -> {ctl}: {r.rowcount} row(s)")

    db.session.commit()
    print("All data migrations committed")
