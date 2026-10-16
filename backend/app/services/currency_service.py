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
            to_currency: str | None = None, actor_id, journal_code: str = "GEN"):
    """إعادة تقييم أرصدة حسابات بعملات أجنبية: فرق غير محقق بقيد تسوية.

    - الرصيد تراكمي حتى نهاية الفترة (لا حركة فترة واحدة).
    - الرصيد الأجنبي من السطور بعملة الحساب، والقيمة الدفترية من `amount_functional`
      (سعر الصرف التاريخي لكل سطر) — الفرق هو الربح/الخسارة غير المحققة فعلًا.
    - الحساب بلا قيد عملة يُتجاوز (لا افتراض USD).
    """
    from . import posting_service
    from ..models.journal import Journal
    from ..models.account import Account
    from ..models.entity import FiscalPeriod
    tenant_id = uuid.UUID(str(tenant_id))
    entity_id = uuid.UUID(str(entity_id))
    period = db.session.get(FiscalPeriod, uuid.UUID(str(period_id)))
    if period is None or period.is_deleted:
        raise ValidationError("Unknown fiscal period")
    as_of = period.ends_on
    if to_currency is None:
        from ..models.entity import Entity
        ent = db.session.get(Entity, entity_id)
        to_currency = (ent.functional_currency if ent and ent.functional_currency
                       else "JOD")
    lines, total = [], Decimal("0")
    for code in account_codes:
        acc = db.session.query(Account).filter_by(
            tenant_id=tenant_id, entity_id=entity_id,
            code=code, is_deleted=False).first()
        if acc is None:
            raise ValidationError(f"Unknown account {code}")
        cur = acc.currency_restriction
        if not cur:
            continue  # بلا عملة مقيدة — لا يمكن تحديد عملة الرصيد
        bal = db.session.execute(db.text(
            "SELECT COALESCE(SUM(CASE WHEN l.debit > 0 THEN l.amount_currency "
            "ELSE -l.amount_currency END),0)::float, "
            "COALESCE(SUM(CASE WHEN l.debit > 0 THEN l.amount_functional "
            "ELSE -l.amount_functional END),0)::float "
            "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
            "WHERE l.account_id = :a AND l.currency_id = :c "
            "AND e.posting_date <= :d AND e.status IN ('posted','reversed') "
            "AND e.is_deleted = FALSE AND l.is_deleted = FALSE"),
            {"a": acc.id, "c": cur, "d": as_of}).first()
        foreign, carrying = (bal[0] or 0.0), (bal[1] or 0.0)
        if abs(foreign) < 0.001:
            continue
        fx = get_rate(tenant_id=tenant_id, from_currency=cur,
                      to_currency=to_currency, on_date=as_of)
        target = (Decimal(str(foreign)) * fx).quantize(Decimal("0.001"))
        diff = target - Decimal(str(carrying))
        if abs(diff) < 0.001:
            continue
        gain = db.session.query(Account).filter_by(
            tenant_id=tenant_id, entity_id=entity_id,
            code="4095", is_deleted=False).first()
        if gain is None:
            raise ValidationError("Gain/loss account 4095 missing — create it first")
        # سطر الفرق على الحساب الأجنبي يُوسم بعملته وسعر 1 حتى يدخل حساب
        # "القيمة الدفترية" في إعادة التقييم التالية (amount_currency=0 لا
        # يغيّر الرصيد الأجنبي، لكن amount_functional=diff يحدّث الحمل).
        # بدون الوسم كانت السطور تُحفظ بعملة JOD الافتراضية فتُستبعد من
        # استعلام الحمولة (فلترة currency_id) وتُعاد إعادة التقييم كاملة كل فترة.
        fx_line = {"account_id": acc.id, "currency_id": str(cur),
                   "amount_currency": 0, "exchange_rate": 1}
        if diff > 0:
            lines.append({**fx_line, "debit": float(diff), "credit": 0})
            lines.append({"account_id": gain.id, "debit": 0, "credit": float(diff)})
        else:
            lines.append({"account_id": gain.id, "debit": float(-diff), "credit": 0})
            lines.append({**fx_line, "debit": 0, "credit": float(-diff)})
        total += abs(diff)
    if not lines:
        return {"revalued": 0.0, "entry_id": None}
    journal = db.session.query(Journal).filter_by(
        tenant_id=tenant_id, entity_id=entity_id,
        code=journal_code, is_deleted=False).first()
    if journal is None:
        raise NotFoundError(f"Journal {journal_code} not configured")
    entry = posting_service.create_entry(
        {"tenant_id": tenant_id, "entity_id": entity_id, "journal_id": journal.id,
         "entry_type": "revaluation", "document_date": as_of, "posting_date": as_of,
         "description": "إعادة تقييم عملات", "source_module": "fx",
         "source_event_key": f"fx.reval.{period_id}.{to_currency}.{as_of.isoformat()}.v1"},
        lines, actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    return {"revalued": float(total), "entry_id": str(entry.id),
            "official_number": entry.official_number}
