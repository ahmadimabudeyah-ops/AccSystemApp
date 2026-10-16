"""Chart-of-accounts dry-run: read-only classification, no writes.

Usage:  python scripts/dry_run_chart.py [TENANT_CODE] [ENTITY_CODE]
Distinguishes: healthy roots / legacy-unclassified / risky (cycles,
cross-entity parents, missing parents, family mismatches, role/postable
contradictions). Also reports: empty closure, is_leaf drift, mixed-currency
posted lines, locked-code accounts inventory.
"""
import sys

sys.path.insert(0, ".")
from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services import chart_service as chart  # noqa: E402

app = create_app()
tenant_code = sys.argv[1] if len(sys.argv) > 1 else "DEMO"
entity_code = sys.argv[2] if len(sys.argv) > 2 else "MAIN"

with app.app_context():
    from app.models.tenant import Tenant
    from app.models.entity import Entity
    t = db.session.query(Tenant).filter_by(code=tenant_code).first()
    if t is None:
        print(f"UNKNOWN TENANT {tenant_code}")
        sys.exit(2)
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    e = db.session.query(Entity).filter_by(tenant_id=t.id, code=entity_code).first()
    if e is None:
        have = [x.code for x in db.session.query(Entity).filter_by(tenant_id=t.id).all()]
        print(f"UNKNOWN ENTITY {entity_code} (have: {have})")
        sys.exit(2)

    diag = chart.diagnose(tenant_id=t.id, entity_id=e.id)
    print(f"tenant={tenant_code} entity={entity_code} total={diag['counts']['total']} "
          f"healthy={diag['counts']['healthy']} "
          f"unclassified={diag['counts']['unclassified']} "
          f"risky={diag['counts']['risky']}")
    if diag["unclassified"]:
        print("--- unclassified (legacy, kept as-is) ---")
        for u in diag["unclassified"][:30]:
            print(f"  {u['code']} {u['name_ar']}")
        if len(diag["unclassified"]) > 30:
            print(f"  ... +{len(diag['unclassified']) - 30}")
    if diag["risky"]:
        print("--- RISKY (blocks new operations on affected nodes) ---")
        for r in diag["risky"]:
            print(f"  {r.get('code')} {r.get('name_ar')}: {'; '.join(r['problems'])}")
    else:
        print("--- no risky relations ---")

    closure = db.session.execute(text(
        "SELECT count(*) FROM account_hierarchy h JOIN accounts a "
        "ON a.id = h.descendant_id WHERE a.tenant_id = :t AND a.entity_id = :e"),
        {"t": str(t.id), "e": str(e.id)}).scalar()
    print(f"closure rows for scope: {closure}")
    drift = db.session.execute(text("""
        SELECT a.code FROM accounts a WHERE a.tenant_id = :t AND a.entity_id = :e
        AND a.is_deleted = FALSE AND a.is_leaf <>
          (NOT EXISTS (SELECT 1 FROM accounts c WHERE c.parent_id = a.id
                       AND c.is_deleted = FALSE))"""),
        {"t": str(t.id), "e": str(e.id)}).fetchall()
    print(f"is_leaf drift: {[d[0] for d in drift] or 'none'}")
    mixed = db.session.execute(text("""
        SELECT DISTINCT l.currency_id, l.exchange_rate FROM journal_lines l
        JOIN journal_entries je ON je.id = l.entry_id
        JOIN accounts a ON a.id = l.account_id
        WHERE a.tenant_id = :t AND a.entity_id = :e AND je.status = 'posted'
        AND je.is_deleted = FALSE AND l.is_deleted = FALSE
        AND (l.exchange_rate <> 1)"""),
        {"t": str(t.id), "e": str(e.id)}).fetchall()
    print(f"non-1-rate posted lines: {mixed or 'none (single-currency reality)'}")
    locked = db.session.execute(text(
        "SELECT code, name_ar FROM accounts WHERE tenant_id = :t AND entity_id = :e "
        "AND is_deleted = FALSE AND code IN ('1210','4010','2140','2010','1310','4095') "
        "ORDER BY code"), {"t": str(t.id), "e": str(e.id)}).fetchall()
    print(f"locked service codes present: {[dict(code=c, name=n) for c, n in locked]}")
