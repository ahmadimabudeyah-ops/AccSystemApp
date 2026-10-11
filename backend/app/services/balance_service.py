"""BalanceService — الأرصدة والميزان والأستاذ واللقطات.

Golden rule: balances always derive from POSTED lines. Caches are advisory.
"""
from __future__ import annotations
import hashlib
import json
import logging
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import func
from ..extensions import db
from ..models.journal import JournalEntry, JournalLine

log = logging.getLogger(__name__)


def _posted_lines():
    return (
        db.session.query(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(JournalEntry.status == "posted",
                JournalEntry.is_deleted.is_(False),
                JournalLine.is_deleted.is_(False))
    )


def get_account_balance(account_id: uuid.UUID, as_of: date | None = None) -> dict:
    """رصيد حساب حتى تاريخ (مدين - دائن)."""
    q = _posted_lines().filter(JournalLine.account_id == account_id)
    if as_of is not None:
        q = q.filter(JournalEntry.posting_date <= as_of)
    debit, credit = q.with_entities(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0)).first()
    debit, credit = Decimal(debit), Decimal(credit)
    return {"account_id": str(account_id), "debit": float(debit),
            "credit": float(credit), "balance": float(debit - credit)}


def get_trial_balance(period_id: uuid.UUID) -> dict:
    """ميزان المراجعة لفترة — يجب أن يكون متوازنًا دائمًا."""
    rows = (
        db.session.query(JournalLine.account_id,
                         func.sum(JournalLine.debit).label("debit"),
                         func.sum(JournalLine.credit).label("credit"))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(JournalEntry.period_id == period_id,
                JournalEntry.status == "posted",
                JournalEntry.is_deleted.is_(False),
                JournalLine.is_deleted.is_(False))
        .group_by(JournalLine.account_id).all()
    )
    lines = [{"account_id": str(r.account_id), "debit": float(r.debit or 0),
              "credit": float(r.credit or 0)} for r in rows]
    total_d = sum(l["debit"] for l in lines)
    total_c = sum(l["credit"] for l in lines)
    return {"period_id": str(period_id), "lines": lines,
            "total_debit": total_d, "total_credit": total_c,
            "balanced": abs(total_d - total_c) < 0.001}


def get_ledger(account_id: uuid.UUID, date_from: date, date_to: date,
               *, limit: int = 500, offset: int = 0) -> dict:
    """الأستاذ العام لحساب في مدى زمني مع الرصيد الافتتاحي."""
    opening = get_account_balance(account_id, as_of=date_from - __import__("datetime").timedelta(days=1))
    q = (
        _posted_lines().filter(JournalLine.account_id == account_id,
                               JournalEntry.posting_date.between(date_from, date_to))
        .order_by(JournalEntry.posting_date, JournalEntry.official_number)
    )
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    running = opening["balance"]
    lines = []
    for l in rows:
        running += float(l.debit - l.credit)
        lines.append({"entry_id": str(l.entry_id), "line_number": l.line_number,
                      "posting_date": l.entry.posting_date.isoformat(),
                      "official_number": l.entry.official_number,
                      "description": l.description or l.entry.description,
                      "debit": float(l.debit), "credit": float(l.credit),
                      "running_balance": running})
    return {"account_id": str(account_id), "opening_balance": opening["balance"],
            "lines": lines, "closing_balance": running,
            "total": total, "limit": limit, "offset": offset}


def build_snapshot(period_id: uuid.UUID) -> dict:
    """لقطة إقفال مجمدة: ميزان + بصمة hash للتحقق من الثبات."""
    tb = get_trial_balance(period_id)
    fingerprint = hashlib.sha256(
        json.dumps(tb["lines"], sort_keys=True, default=str).encode()).hexdigest()
    log.info("snapshot built period=%s hash=%s", period_id, fingerprint)
    return {"period_id": str(period_id), "trial_balance": tb,
            "hash": fingerprint, "taken_at": date.today().isoformat()}


def _statement(period_id: uuid.UUID, report_code: str) -> dict:
    """قائمة مالية من خرائط التقارير + الميزان (BS/PL).

    كل بند = مجموع أرصدة حساباته × الإشارة (plus/minus). الحسابات بلا خريطة
    تُسند تلقائيًا حسب نوعها (asset/liability/equity→BS، income/expense→PL).
    """
    from sqlalchemy import text as _text
    tenant_id = db.session.execute(
        _text("SELECT tenant_id FROM fiscal_periods WHERE id = :p"), {"p": period_id}
    ).scalar()
    tb = {l["account_id"]: l for l in get_trial_balance(period_id)["lines"]}
    maps = db.session.execute(_text(
        "SELECT m.account_id::text, m.line_code, m.sign, a.account_type "
        "FROM account_report_mappings m JOIN accounts a ON a.id = m.account_id "
        "WHERE m.tenant_id = :t AND m.report_code = :r AND m.is_deleted = FALSE "
        "AND a.is_deleted = FALSE"), {"t": tenant_id, "r": report_code}).all()
    if not maps:
        auto = {"BS": {"asset": "BS.ASSETS", "contra_asset": "BS.ASSETS",
                       "liability": "BS.LIABILITIES", "equity": "BS.EQUITY"},
                "PL": {"income": "PL.REVENUE", "contra_income": "PL.REVENUE",
                       "expense": "PL.EXPENSES", "contra_expense": "PL.EXPENSES"}}
        rows = db.session.execute(_text(
            "SELECT id::text, account_type FROM accounts "
            "WHERE tenant_id = :t AND is_deleted = FALSE"), {"t": tenant_id}).all()
        maps = [(aid, auto[report_code].get(at, "OTHER"),
                 "minus" if at.startswith("contra_") else "plus", at)
                for aid, at in rows if at in auto[report_code]]
    else:
        maps = [(aid, line, sign, None) for aid, line, sign in maps]
    # العرض بالرصيد الطبيعي: المدين-طبيعي موجب، والدائن-طبيعي يُعكس ليظهر موجبًا
    CREDIT_NORMAL = {"liability", "equity", "income", "contra_asset", "contra_expense"}
    buckets: dict[str, float] = {}
    for account_id, line_code, sign, atype in maps:
        line = tb.get(str(account_id))
        net = (line["debit"] - line["credit"]) if line else 0.0
        if sign == "minus":
            net = -net
        if atype is None:
            atype = db.session.execute(_text(
                "SELECT account_type FROM accounts WHERE id = :a"), {"a": account_id}).scalar()
        if atype in CREDIT_NORMAL:
            net = -net
        buckets[line_code] = buckets.get(line_code, 0.0) + net
    lines = [{"line_code": k, "amount": round(v, 3)} for k, v in sorted(buckets.items())]
    return {"period_id": str(period_id), "report": report_code,
            "lines": lines, "total": round(sum(buckets.values()), 3)}


def get_balance_sheet(period_id: uuid.UUID) -> dict:
    """الميزانية العمومية لفترة."""
    return _statement(period_id, "BS")


def get_income_statement(period_id: uuid.UUID) -> dict:
    """قائمة الدخل لفترة."""
    return _statement(period_id, "PL")


def get_dashboard_summary(entity_id: uuid.UUID) -> dict:
    """ملخص اللوحة: إيراد/مصروف/ربح (مرحّل) + أشهر الستة الأخيرة."""
    from sqlalchemy import text as _text
    from datetime import date as _date
    rows = db.session.execute(_text(
        "SELECT a.account_type, date_trunc('month', e.posting_date)::date AS m, "
        "SUM(l.credit - l.debit)::float AS net "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "JOIN accounts a ON a.id = l.account_id "
        "WHERE e.entity_id = :en AND e.status = 'posted' "
        "AND e.is_deleted = FALSE AND l.is_deleted = FALSE "
        "GROUP BY 1, 2 ORDER BY 2"), {"en": entity_id}).all()
    revenue = sum(r[2] for r in rows if r[0] in ("income",))
    expenses = -sum(r[2] for r in rows if r[0] in ("expense", "contra_income"))
    months: dict[str, float] = {}
    for _type, m, net in rows:
        if _type == "income" and m:
            months[m.isoformat()[:7]] = months.get(m.isoformat()[:7], 0.0) + net
    last6 = sorted(months)[-6:]
    pending = db.session.execute(_text(
        "SELECT (SELECT count(*) FROM journal_entries WHERE entity_id = :en AND status = 'draft' AND is_deleted = FALSE), "
        "(SELECT count(*) FROM customer_invoices i JOIN parties p ON p.id = i.customer_id "
        " WHERE p.entity_id = :en AND i.status IN ('posted','partially_paid') AND i.remaining_amount > 0 "
        " AND i.due_on < CURRENT_DATE AND i.is_deleted = FALSE)"),
        {"en": entity_id}).first()
    return {"revenue": round(revenue, 3), "expenses": round(expenses, 3),
            "profit": round(revenue - expenses, 3),
            "months": last6, "monthly_revenue": [round(months[m], 3) for m in last6],
            "pending_drafts": pending[0] if pending else 0,
            "overdue_invoices": pending[1] if pending else 0,
            "as_of": _date.today().isoformat()}
