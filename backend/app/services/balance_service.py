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

"""BalanceService — الأرصدة والميزان والأستاذ واللقطات.

Golden rule: balances always derive from POSTED lines. Caches are advisory.

عقد المبالغ والعملات (موثق بعد فحص المحرك):
- سطر القيد يحمل debit/credit (عملة القيد) وamount_currency (مبلغ العملة)
  وamount_functional (المكافئ الوظيفي وقت الترحيل = المبلغ × السعر).
- كل البيانات المرحلة الحية أحادية العملة (JOD×1) — الجمع على debit/credit
  صحيح واقعيًا. أي خلط عملات في نطاق التقرير يُرفع كتحذير
  mixed_currency صريح بدل رقم مختلط صامت؛ ولا تُعاد كتابة التاريخ.
"""

CREDIT_NORMAL = {"liability", "equity", "income", "contra_asset", "contra_expense"}

# حالات القيد ذات الأثر المرحل: المعكوس (reversed) يبقى مرحّلًا —
# قيد العكس بتاريخه هو ما يقابله. إسقاط الأصل يختل معه التقرير السابق.
POSTED_STATUSES = ("posted", "reversed")

log = logging.getLogger(__name__)


def _posted_lines():
    return (
        db.session.query(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(JournalEntry.status.in_(POSTED_STATUSES),
                JournalEntry.is_deleted.is_(False),
                JournalLine.is_deleted.is_(False))
    )


def _scope_ids(account_id: uuid.UUID, mode: str) -> list[uuid.UUID]:
    """نطاق التجميع: المباشر = الحساب نفسه؛ المجمع = هو + نسله.

    يستخدم path (يصونه المشغل) لا جدول الإغلاق وحده — كل سطر حركة يُحتسب
    مرة واحدة حتى مع حركات legacy المباشرة على حساب له أبناء.
    """
    from sqlalchemy import text as _text
    if mode == "direct":
        return [account_id]
    acc = db.session.execute(_text(
        "SELECT path FROM accounts WHERE id = :i"), {"i": str(account_id)}).first()
    if acc is None:
        return [account_id]
    rows = db.session.execute(_text(
        "SELECT id FROM accounts WHERE is_deleted = FALSE "
        "AND (id = :i OR path = :p OR path LIKE :like)"),
        {"i": str(account_id), "p": acc[0], "like": acc[0] + ".%"}).fetchall()
    return [r[0] for r in rows]


def _currency_health(account_ids: list) -> dict:
    """فحص تجانس العملة في النطاق: أي سعر صرف ≠1 أو عملات متعددة = تحذير."""
    from sqlalchemy import text as _text, bindparam as _bp
    ids = [str(i) for i in account_ids] or ["00000000-0000-0000-0000-000000000000"]
    stmt = _text(
        "SELECT count(DISTINCT l.currency_id), "
        "SUM(CASE WHEN l.exchange_rate <> 1 THEN 1 ELSE 0 END) "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "WHERE l.account_id IN :ids AND l.is_deleted = FALSE "
        "AND e.status IN ('posted','reversed') AND e.is_deleted = FALSE").bindparams(
            _bp("ids", expanding=True))
    row = db.session.execute(stmt, {"ids": ids}).first()
    ncur = int(row[0] or 0)
    mixed = ncur > 1 or int(row[1] or 0) > 0
    cur = None
    if ncur == 1:
        cur = db.session.execute(_text(
            "SELECT DISTINCT l.currency_id FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.entry_id "
            "WHERE l.account_id IN :lids AND l.is_deleted = FALSE "
            "AND e.status IN ('posted','reversed') AND e.is_deleted = FALSE").bindparams(
                _bp("lids", expanding=True)), {"lids": ids}).scalar()
    return {"mixed": mixed, "currency": cur}


def get_account_balance(account_id: uuid.UUID, as_of: date | None = None,
                        mode: str = "direct") -> dict:
    """رصيد حساب حتى تاريخ (مدين - دائن)، مباشر أو مجمع.

    - المباشر: حركات الحساب نفسه فقط.
    - المجمع: حركاته + نسلِه، كل سطر مرة واحدة (يشمل legacy المباشرة).
    - الافتتاحي/الفترة/الختامي تُشتق منه في التقارير لا هنا.
    """
    from sqlalchemy import text as _text
    ids = _scope_ids(account_id, mode)
    q = _posted_lines().filter(JournalLine.account_id.in_(ids))
    if as_of is not None:
        q = q.filter(JournalEntry.posting_date <= as_of)
    debit, credit = q.with_entities(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0)).first()
    debit, credit = Decimal(debit), Decimal(credit)
    health = _currency_health(ids)
    ent_cur = db.session.execute(_text(
        "SELECT e.functional_currency FROM entities e "
        "JOIN accounts a ON a.entity_id = e.id WHERE a.id = :i"),
        {"i": str(account_id)}).scalar()
    return {"account_id": str(account_id), "mode": mode,
            "debit": float(debit), "credit": float(credit),
            "balance": float(debit - credit),
            "functional_currency": ent_cur,
            "mixed_currency": health["mixed"],
            "line_currency": health["currency"]}


def get_trial_balance(period_id: uuid.UUID, *, with_parents: bool = False) -> dict:
    """ميزان المراجعة لفترة — يجب أن يكون متوازنًا دائمًا.

    الإجماليات دائمًا من سطور فريدة (لا يُجمع الأب مع أبنائه).
    with_parents=True يضيف صفوف الآباء (display_only) للعرض فقط.
    """
    rows = (
        db.session.query(JournalLine.account_id,
                         func.sum(JournalLine.debit).label("debit"),
                         func.sum(JournalLine.credit).label("credit"))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(JournalEntry.period_id == period_id,
                JournalEntry.status.in_(POSTED_STATUSES),
                JournalEntry.is_deleted.is_(False),
                JournalLine.is_deleted.is_(False))
        .group_by(JournalLine.account_id).all()
    )
    acc_map: dict[str, dict] = {}
    if rows:
        from ..models.account import Account
        for a in db.session.query(Account).filter(
                Account.id.in_([r.account_id for r in rows])).all():
            acc_map[str(a.id)] = {"code": a.code, "name_ar": a.name_ar}
    lines = [{"account_id": str(r.account_id),
              "account_code": (acc_map.get(str(r.account_id)) or {}).get("code"),
              "account_name": (acc_map.get(str(r.account_id)) or {}).get("name_ar"),
              "debit": float(r.debit or 0),
              "credit": float(r.credit or 0)} for r in rows]
    total_d = sum(l["debit"] for l in lines)
    total_c = sum(l["credit"] for l in lines)
    out = {"period_id": str(period_id), "lines": lines,
           "total_debit": total_d, "total_credit": total_c,
           "balanced": abs(total_d - total_c) < 0.001}
    if with_parents and lines:
        out["parent_rows"] = _aggregate_parents(lines)
    return out


def _aggregate_parents(lines: list[dict]) -> list[dict]:
    """صفوف تجميعية للآباء من السطور الفريدة — للعرض فقط (display_only)."""
    from sqlalchemy import text as _text, bindparam as _bp
    by_acc = {l["account_id"]: l for l in lines}
    accs = db.session.execute(_text(
        "SELECT id::text, parent_id::text, code, name_ar FROM accounts "
        "WHERE id IN :ids AND is_deleted = FALSE").bindparams(
            _bp("ids", expanding=True)),
        {"ids": list(by_acc)}).fetchall()
    info = {a[0]: a for a in accs}
    agg: dict[str, dict] = {}
    for aid, l in by_acc.items():
        cur = info.get(aid)
        seen = set()
        while cur and cur[1] and cur[1] not in seen:
            seen.add(cur[1])
            p = db.session.execute(_text(
                "SELECT id::text, parent_id::text, code, name_ar FROM accounts "
                "WHERE id = :i AND is_deleted = FALSE"), {"i": cur[1]}).first()
            if p is None:
                break
            a = agg.setdefault(p[0], {"account_id": p[0], "code": p[2],
                                      "name_ar": p[3], "debit": 0.0, "credit": 0.0,
                                      "display_only": True})
            a["debit"] += l["debit"]
            a["credit"] += l["credit"]
            cur = p
    return sorted(agg.values(), key=lambda r: r["code"])


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


def _resolve_mappings(tenant_id, report_code: str) -> list[tuple]:
    """الربط المباشر أولًا، ثم وراثة أقرب سلف مربوط.

    - الحساب المربوط مباشرة يستخدم ربطه.
    - غير المربوط يرث أقرب سلف مربوط (إن وجد).
    - أب وابن مربوطان لسطرين مختلفين = تعارض إعداد (409 صريح) لا جمع مزدوج.
    """
    from sqlalchemy import text as _text
    from .errors import ReportConfigError
    rows = db.session.execute(_text(
        "SELECT id::text, parent_id::text, account_type FROM accounts "
        "WHERE tenant_id = :t AND is_deleted = FALSE"), {"t": tenant_id}).all()
    info = {r[0]: (r[1], r[2]) for r in rows}
    direct = {r[0]: (r[1], r[2]) for r in db.session.execute(_text(
        "SELECT m.account_id::text, m.line_code, m.sign "
        "FROM account_report_mappings m "
        "WHERE m.tenant_id = :t AND m.report_code = :r AND m.is_deleted = FALSE"),
        {"t": tenant_id, "r": report_code}).all()}
    if not direct:
        return []
    # كشف التعارض: مربوط له نسل مربوط بسطر مختلف
    conflicts = []
    for aid, (line, _sign) in direct.items():
        desc = db.session.execute(_text(
            "SELECT c.id::text FROM accounts c JOIN accounts p ON p.id = :i "
            "WHERE c.is_deleted = FALSE AND c.path LIKE p.path || '.%'"),
            {"i": aid}).fetchall()
        for (did,) in desc:
            if did in direct and direct[did][0] != line:
                conflicts.append({"account_id": aid, "line": line,
                                  "descendant_id": did,
                                  "descendant_line": direct[did][0]})
    if conflicts:
        raise ReportConfigError(
            "تعارض إعداد التقارير (أب وابن لسطرين مختلفين): " +
            "; ".join(f"{c['account_id']}->{c['line']} vs "
                      f"{c['descendant_id']}->{c['descendant_line']}"
                      for c in conflicts[:5]))
    resolved = []
    for aid, (parent, atype) in info.items():
        if aid in direct:
            line, sign = direct[aid]
            resolved.append((aid, line, sign, atype))
            continue
        cur, seen = parent, set()
        while cur and cur not in seen:
            seen.add(cur)
            if cur in direct:
                line, sign = direct[cur]
                resolved.append((aid, line, sign, atype))
                break
            cur = info[cur][0] if cur in info else None
    return resolved


def _cumulative_balances(entity_id, as_of) -> dict[str, dict]:
    """أرصدة تراكمية لكل حساب (كل الفترات) حتى تاريخ — أساس الميزانية العمومية.

    تختلف عن get_trial_balance(period) التي تحصر الحركات في فترة واحدة؛
    الميزانية يجب أن تعكس الأرصدة المتراكمة حتى تاريخ التقرير.
    """
    from sqlalchemy import text as _text
    rows = db.session.execute(_text(
        "SELECT l.account_id::text, SUM(l.debit) AS d, SUM(l.credit) AS c "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
        "AND e.is_deleted = FALSE AND l.is_deleted = FALSE AND e.posting_date <= :dt "
        "GROUP BY 1"), {"en": entity_id, "dt": as_of}).fetchall()
    return {r[0]: {"debit": float(r[1] or 0), "credit": float(r[2] or 0)} for r in rows}


def _cumulative_net_income(entity_id, as_of) -> float:
    """صافي الدخل التراكمي حتى تاريخ (إيرادات − مصروفات).

    لا توجد قيود إقفال في النظام، فتُحتسب الأرباح غير المُرحّلة هنا وتُعرض
    ضمن حقوق الملكية حتى توازن الميزانية (أصول = التزامات + حقوق + أرباح).
    """
    from sqlalchemy import text as _text
    return float(db.session.execute(_text(
        "SELECT COALESCE(SUM(l.credit - l.debit), 0) "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "JOIN accounts a ON a.id = l.account_id "
        "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
        "AND e.is_deleted = FALSE AND l.is_deleted = FALSE AND e.posting_date <= :dt "
        "AND a.account_type IN ('income','contra_income','expense','contra_expense')"),
        {"en": entity_id, "dt": as_of}).scalar() or 0)


def _statement(period_id: uuid.UUID, report_code: str, *, cumulative: bool = False) -> dict:
    """قائمة مالية من خرائط التقارير + أرصدة الحسابات (BS/PL).

    كل بند = مجموع أرصدة حساباته × الإشارة (plus/minus). الحسابات بلا خريطة
    تُسند تلقائيًا حسب نوعها (asset/liability/equity→BS، income/expense→PL).

    cumulative=True (للميزانية العمومية): الأرصدة تراكمية حتى نهاية الفترة،
    وتُضاف أرباح غير مرحّلة لقسم حقوق الملكية. قائمة الدخل تبقى حصرًا فترة واحدة.
    """
    from sqlalchemy import text as _text
    tenant_id, entity_id, ends_on = db.session.execute(
        _text("SELECT tenant_id, entity_id, ends_on FROM fiscal_periods WHERE id = :p"),
        {"p": period_id}).first()
    if cumulative:
        tb = {aid: {"debit": v["debit"], "credit": v["credit"]}
              for aid, v in _cumulative_balances(entity_id, ends_on).items()}
    else:
        tb = {l["account_id"]: l for l in get_trial_balance(period_id)["lines"]}
    maps = db.session.execute(_text(
        "SELECT m.account_id::text, m.line_code, m.sign, a.account_type "
        "FROM account_report_mappings m JOIN accounts a ON a.id = m.account_id "
        "WHERE m.tenant_id = :t AND m.report_code = :r AND m.is_deleted = FALSE "
        "AND a.is_deleted = FALSE"), {"t": tenant_id, "r": report_code}).all()
    if maps:
        # ربط مباشر + وراثة أقرب سلف + كشف تعارض الأب/الابن (409 صريح).
        resolved = _resolve_mappings(tenant_id, report_code)
    else:
        auto = {"BS": {"asset": "BS.ASSETS", "contra_asset": "BS.ASSETS",
                       "liability": "BS.LIABILITIES", "equity": "BS.EQUITY"},
                "PL": {"income": "PL.REVENUE", "contra_income": "PL.REVENUE",
                       "expense": "PL.EXPENSES", "contra_expense": "PL.EXPENSES"}}
        rows = db.session.execute(_text(
            "SELECT id::text, account_type FROM accounts "
            "WHERE tenant_id = :t AND is_deleted = FALSE"), {"t": tenant_id}).all()
        resolved = [(aid, auto[report_code].get(at, "OTHER"),
                     "minus" if at.startswith("contra_") else "plus", at)
                    for aid, at in rows if at in auto[report_code]]
    # العرض بالرصيد الطبيعي: المدين-طبيعي موجب، والدائن-طبيعي يُعكس ليظهر موجبًا
    buckets: dict[str, float] = {}
    for account_id, line_code, sign, atype in resolved:
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
    if report_code == "BS" and cumulative:
        # أرباح غير مُرحّلة (لا توجد قيود إقفال): تُضاف لحقوق الملكية ليتوازن
        # الجدول المحاسبي: أصول = التزامات + حقوق + أرباح تراكمية.
        buckets["BS.CURRENT_EARNINGS"] = (
            buckets.get("BS.CURRENT_EARNINGS", 0.0) + _cumulative_net_income(entity_id, ends_on))
    lines = [{"line_code": k, "amount": round(v, 3)} for k, v in sorted(buckets.items())]
    return {"period_id": str(period_id), "report": report_code,
            "as_of": ends_on.isoformat() if cumulative else None,
            "basis": "cumulative" if cumulative else "period",
            "lines": lines, "total": round(sum(buckets.values()), 3)}


def get_balance_sheet(period_id: uuid.UUID) -> dict:
    """الميزانية العمومية حتى نهاية الفترة (أرصدة تراكمية + أرباح غير مرحّلة)."""
    return _statement(period_id, "BS", cumulative=True)


def get_income_statement(period_id: uuid.UUID) -> dict:
    """قائمة الدخل لفترة واحدة (حركة الفترة فقط — صحيحة محاسبيًا)."""
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
        "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
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
    mix = db.session.execute(_text(
        "SELECT a.name_ar, SUM(l.credit - l.debit)::float AS net "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "JOIN accounts a ON a.id = l.account_id "
        "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
        "AND e.is_deleted = FALSE AND l.is_deleted = FALSE "
        "AND a.account_type IN ('income','contra_income') "
        "GROUP BY 1 ORDER BY 2 DESC"), {"en": entity_id}).all()
    top = [(n or "؟", round(v or 0, 3)) for n, v in mix if (v or 0) > 0][:3]
    others = round(sum(v for _, v in [(n, v) for n, v in mix if (v or 0) > 0][3:]), 3)
    if others > 0:
        top.append(("أخرى", others))
    cur = db.session.execute(_text(
        "SELECT functional_currency FROM entities WHERE id = :en"), {"en": entity_id}).scalar()
    cash = db.session.execute(_text(
        "SELECT COALESCE(SUM(l.debit - l.credit),0)::float FROM journal_lines l "
        "JOIN journal_entries e ON e.id = l.entry_id JOIN accounts a ON a.id = l.account_id "
        "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
        "AND e.is_deleted = FALSE AND l.is_deleted = FALSE "
        "AND (a.code LIKE '101%' OR a.code LIKE '102%')"), {"en": entity_id}).scalar() or 0.0

    def _direct(code):
        return db.session.execute(_text(
            "SELECT COALESCE(SUM(l.debit - l.credit),0)::float FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.entry_id JOIN accounts a ON a.id = l.account_id "
            "WHERE e.entity_id = :en AND e.status IN ('posted','reversed') "
            "AND e.is_deleted = FALSE AND l.is_deleted = FALSE AND a.code = :c"),
            {"en": entity_id, "c": code}).scalar() or 0.0

    overdue_list = db.session.execute(_text(
        "SELECT i.doc_number, p.name_ar, i.due_on::text, i.remaining_amount::float, "
        "(CURRENT_DATE - i.due_on) AS late_days FROM customer_invoices i "
        "JOIN parties p ON p.id = i.customer_id "
        "WHERE p.entity_id = :en AND i.status IN ('posted','partially_paid') "
        "AND i.remaining_amount > 0 AND i.due_on < CURRENT_DATE AND i.is_deleted = FALSE "
        "ORDER BY i.due_on LIMIT 5"), {"en": entity_id}).all()
    return {"revenue": round(revenue, 3), "expenses": round(expenses, 3),
            "profit": round(revenue - expenses, 3),
            "cash": round(cash, 3),
            "receivables": round(_direct("1210"), 3),
            "payables": round(-_direct("2010"), 3),
            "overdue_list": [{"doc": r[0], "customer": r[1], "due_on": r[2],
                              "remaining": float(r[3]), "late_days": int(r[4] or 0)}
                             for r in overdue_list],
            "months": last6, "monthly_revenue": [round(months[m], 3) for m in last6],
            "revenue_mix": {"labels": [n for n, _ in top], "values": [v for _, v in top]},
            "functional_currency": cur or "JOD",
            "pending_drafts": pending[0] if pending else 0,
            "overdue_invoices": pending[1] if pending else 0,
            "as_of": _date.today().isoformat()}
