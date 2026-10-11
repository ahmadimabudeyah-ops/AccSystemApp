"""Customer portal: magic-link, read-only invoices + statement (no login)."""
import hashlib
from datetime import datetime, timezone
from flask import Blueprint, render_template, abort
from sqlalchemy import text as _text
from ..extensions import db
from ..models.party import Party
from ..models.biz import PortalToken

bp = Blueprint("web_portal", __name__, url_prefix="/portal")


def _token(raw: str):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    row = db.session.execute(
        _text("SELECT tenant_id, party_id, scope, expires_at FROM portal_resolve(:h)"),
        {"h": digest}).first()
    if row is None or row[3].replace(tzinfo=None) < datetime.utcnow():
        abort(404)
    # قيد الجلسة على مستأجر التوكن فقط — كل قراءة لاحقة خاضعة لـ RLS
    db.session.execute(_text("SET LOCAL \"app.current_tenant_id\" = :t"),
                       {"t": str(row[0])})
    tok = db.session.query(PortalToken).filter_by(token_hash=digest).first()
    if tok:
        tok.last_used_at = datetime.utcnow()
        db.session.commit()
        db.session.execute(_text("SET LOCAL \"app.current_tenant_id\" = :t"),
                           {"t": str(row[0])})
    return row[1]


@bp.get("/<raw>")
def statement(raw):
    party = db.session.get(Party, _token(raw))
    return render_template("portal/statement.html", party=party, tok=None, raw=raw,
                           crumbs=[("البوابة", None)], active="")


@bp.get("/<raw>/invoices")
def invoices(raw):
    from ..models.sales import CustomerInvoice
    party_id = _token(raw)
    rows = db.session.query(CustomerInvoice).filter_by(
        customer_id=party_id, is_deleted=False).order_by(CustomerInvoice.invoice_date.desc()).all()
    return render_template("portal/invoices.html", invoices=rows,
                           crumbs=[("البوابة", None)], active="")
