"""Debug portal resolve with real hash."""
import hashlib
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    raw = "test-raw-token-123"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.session.execute(text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    from app.models.biz import PortalToken  # noqa: E402
    from app.models.party import Party  # noqa: E402
    from datetime import datetime, timedelta  # noqa: E402
    p = db.session.query(Party).first()
    print("party:", p.id if p else None)
    tok = PortalToken(tenant_id=p.tenant_id, party_id=p.id, token_hash=digest,
                      scope="statement", expires_at=datetime.utcnow() + timedelta(days=1))
    db.session.add(tok)
    db.session.commit()
    row = db.session.execute(text("SELECT * FROM portal_resolve(:h)"), {"h": digest}).first()
    print("RESOLVED:", row)
