"""Currency service: FX lookup, conversion, period revaluation (unrealized)."""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.biz import ExchangeRate
from .errors import NotFoundError, ValidationError

log = logging.getLogger(__name__)


def get_rate(*, tenant_id, from_currency: str, to_currency: str, on_date: date | None = None) -> Decimal:
    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    if from_currency == to_currency:
        return Decimal("1")
    row = (db.session.query(ExchangeRate)
           .filter_by(tenant_id=uuid.UUID(str(tenant_id)), from_currency=from_currency,
                      to_currency=to_currency, is_deleted=False)
           .filter(ExchangeRate.rate_date <= (on_date or date.today()))
           .order_by(ExchangeRate.rate_date.desc()).first())
    if row is None:
        raise NotFoundError(f"No rate {from_currency}->{to_currency}")
    return Decimal(str(row.rate))


def convert(amount, *, tenant_id, from_currency: str, to_currency: str,
            on_date: date | None = None) -> Decimal:
    return (Decimal(str(amount)) * get_rate(
        tenant_id=tenant_id, from_currency=from_currency,
        to_currency=to_currency, on_date=on_date)).quantize(Decimal("0.001"))


def revalue(*, tenant_id, entity_id, period_id, account_codes: list[str],
            to_currency: str = "JOD", actor_id, journal_code: str = "GEN"):
    """إعادة تقييم أرصدة حسابات بعملات أجنبية: فرق غير محقق بقيد تسوية."""
    from . import posting_service
    from ..models.journal import Journal
    from ..models.account import Account
    tenant_id = uuid.UUID(str(tenant_id))
    lines, total = [], Decimal("0")
    for code in account_codes:
        acc = db.session.query(Account).filter_by(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
            code=code, is_deleted=False).first()
        if acc is None:
            raise ValidationError(f"Unknown account {code}")
        bal = db.session.execute(db.text(
            "SELECT COALESCE(SUM(l.debit - l.credit),0)::float FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.entry_id "
            "WHERE l.account_id = :a AND e.fiscal_period_id = :p AND e.status = 'posted' "
            "AND e.is_deleted = FALSE AND l.is_deleted = FALSE"),
            {"a": acc.id, "p": str(period_id)}).scalar() or 0.0
        if abs(bal) < 0.001:
            continue
        cur = acc.currency_restriction or "USD"
        fx = get_rate(tenant_id=tenant_id, from_currency=cur, to_currency=to_currency)
        revalued = (Decimal(str(bal)) * fx).quantize(Decimal("0.001"))
        diff = revalued - Decimal(str(bal))
        if abs(diff) < 0.001:
            continue
        gain = db.session.query(Account).filter_by(
            tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
            code="4095", is_deleted=False).first()
        if gain is None:
            raise ValidationError("Gain/loss account 4095 missing — create it first")
        if diff > 0:
            lines.append({"account_id": acc.id, "debit": float(diff), "credit": 0})
            lines.append({"account_id": gain.id, "debit": 0, "credit": float(diff)})
        else:
            lines.append({"account_id": gain.id, "debit": float(-diff), "credit": 0})
            lines.append({"account_id": acc.id, "debit": 0, "credit": float(-diff)})
        total += abs(diff)
    if not lines:
        return {"revalued": 0.0, "entry_id": None}
    journal = db.session.query(Journal).filter_by(
        tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
        code=journal_code, is_deleted=False).first()
    entry = posting_service.create_entry(
        {"tenant_id": tenant_id, "entity_id": uuid.UUID(str(entity_id)), "journal_id": journal.id,
         "entry_type": "revaluation", "document_date": date.today(), "posting_date": date.today(),
         "description": "إعادة تقييم عملات", "source_module": "fx",
         "source_event_key": f"fx.reval.{period_id}.{to_currency}.v1"},
        lines, actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    return {"revalued": float(total), "entry_id": str(entry.id),
            "official_number": entry.official_number}
