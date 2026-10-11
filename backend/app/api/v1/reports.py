"""Reports API — all figures derive from POSTED entries.

GET /api/v1/reports/trial-balance?period_id=
GET /api/v1/reports/ledger?account_id=&from=&to=
GET /api/v1/reports/account-balance?account_id=[&as_of=]
"""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...services import balance_service

bp = Blueprint("reports", __name__)


def _deny(perm: str = "reports.view"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


@bp.get("/trial-balance")
@jwt_required()
def trial_balance():
    denied = _deny()
    if denied:
        return denied
    tb = balance_service.get_trial_balance(uuid.UUID(str(request.args["period_id"])))
    return jsonify({"data": tb})


@bp.get("/ledger")
@jwt_required()
def ledger():
    denied = _deny()
    if denied:
        return denied
    data = balance_service.get_ledger(
        uuid.UUID(str(request.args["account_id"])),
        date.fromisoformat(request.args["from"]), date.fromisoformat(request.args["to"]),
        limit=int(request.args.get("limit", 500)), offset=int(request.args.get("offset", 0)))
    return jsonify({"data": data})


@bp.get("/account-balance")
@jwt_required()
def account_balance():
    denied = _deny()
    if denied:
        return denied
    as_of = request.args.get("as_of")
    data = balance_service.get_account_balance(
        uuid.UUID(str(request.args["account_id"])), date.fromisoformat(as_of) if as_of else None)
    return jsonify({"data": data})


@bp.get("/balance-sheet")
@jwt_required()
def balance_sheet():
    denied = _deny()
    if denied:
        return denied
    data = balance_service.get_balance_sheet(uuid.UUID(str(request.args["period_id"])))
    return jsonify({"data": data})


@bp.get("/income-statement")
@jwt_required()
def income_statement():
    denied = _deny()
    if denied:
        return denied
    data = balance_service.get_income_statement(uuid.UUID(str(request.args["period_id"])))
    return jsonify({"data": data})


@bp.get("/dashboard-summary")
@jwt_required()
def dashboard_summary():
    denied = _deny()
    if denied:
        return denied
    data = balance_service.get_dashboard_summary(uuid.UUID(str(request.args["entity_id"])))
    return jsonify({"data": data})


@bp.get("/cash-flow")
@jwt_required()
def cash_flow():
    denied = _deny()
    if denied:
        return denied
    """التدفقات النقدية: صافي حركة الحسابات النقدية (101*/102*) شهريًا."""
    from sqlalchemy import text as _text
    rows = db.session.execute(_text(
        "SELECT date_trunc('month', e.posting_date)::date AS m, "
        "SUM(CASE WHEN l.debit > 0 THEN l.debit ELSE -l.credit END)::float AS net "
        "FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id "
        "JOIN accounts a ON a.id = l.account_id "
        "WHERE e.entity_id = :en AND e.status = 'posted' AND e.is_deleted = FALSE "
        "AND l.is_deleted = FALSE AND (a.code LIKE '101%' OR a.code LIKE '102%') "
        "GROUP BY 1 ORDER BY 1"),
        {"en": str(request.args["entity_id"])}).all()
    return jsonify({"data": {"months": [{"month": r[0].isoformat()[:7], "net": r[1]} for r in rows],
                             "total": round(sum(r[1] for r in rows), 3)}})


@bp.get("/fiscal-periods")
@jwt_required()
def fiscal_periods():
    from ...models.entity import FiscalPeriod
    from ...extensions import db
    rows = db.session.query(FiscalPeriod).filter_by(
        entity_id=uuid.UUID(str(request.args["entity_id"])), is_deleted=False
    ).order_by(FiscalPeriod.starts_on).all()
    return jsonify({"data": [{"id": str(p.id), "code": p.code, "status": p.status,
                              "starts_on": p.starts_on.isoformat() if p.starts_on else None,
                              "ends_on": p.ends_on.isoformat() if p.ends_on else None} for p in rows]})


def _aging(entity_id, kind: str) -> dict:
    """أعمار الذمم من الأرصدة المتبقية للفواتير المرحّلة."""
    from sqlalchemy import text as _text
    if kind == "receivables":
        rows = db.session.execute(_text(
            "SELECT doc_number, due_on::text, remaining_amount::float, "
            "GREATEST(0, CURRENT_DATE - due_on) AS overdue "
            "FROM customer_invoices WHERE entity_id = :e AND is_deleted = FALSE "
            "AND status IN ('posted','partially_paid') AND remaining_amount > 0.001 "
            "ORDER BY due_on"), {"e": str(entity_id)}).all()
    else:
        rows = db.session.execute(_text(
            "SELECT doc_number, due_on::text, remaining_amount::float, "
            "GREATEST(0, CURRENT_DATE - due_on) AS overdue "
            "FROM vendor_bills WHERE entity_id = :e AND is_deleted = FALSE "
            "AND status IN ('posted','partially_paid') AND remaining_amount > 0.001 "
            "ORDER BY due_on"), {"e": str(entity_id)}).all()
    buckets = {"current": 0.0, "d1_30": 0.0, "d31_60": 0.0, "d61_90": 0.0, "over90": 0.0}
    lines = []
    for doc, due, rem, od in rows:
        od = int(od or 0)
        key = ("current" if od <= 0 else "d1_30" if od <= 30 else "d31_60"
               if od <= 60 else "d61_90" if od <= 90 else "over90")
        buckets[key] = round(buckets[key] + float(rem), 3)
        lines.append({"doc_number": doc, "due_on": due,
                      "remaining": float(rem), "overdue_days": od, "bucket": key})
    buckets["total"] = round(sum(v for v in buckets.values()), 3)
    return {"buckets": buckets, "lines": lines}


@bp.get("/aging-receivables")
@jwt_required()
def aging_receivables():
    denied = _deny()
    if denied:
        return denied
    return jsonify({"data": _aging(uuid.UUID(str(request.args["entity_id"])), "receivables")})


@bp.get("/aging-payables")
@jwt_required()
def aging_payables():
    denied = _deny()
    if denied:
        return denied
    return jsonify({"data": _aging(uuid.UUID(str(request.args["entity_id"])), "payables")})


@bp.get("/inventory")
@jwt_required()
def inventory_report():
    denied = _deny()
    if denied:
        return denied
    from sqlalchemy import text as _text
    rows = db.session.execute(_text(
        "SELECT p.code, p.name_ar, l.code, w.code, q.qty::float, "
        "COALESCE(p.avg_cost,0)::float, (q.qty * COALESCE(p.avg_cost,0))::float "
        "FROM stock_quants q JOIN products p ON p.id = q.product_id "
        "JOIN locations l ON l.id = q.location_id "
        "JOIN warehouses w ON w.id = l.warehouse_id "
        "WHERE w.entity_id = :e AND q.is_deleted = FALSE AND p.is_deleted = FALSE "
        "ORDER BY p.code, l.code"), {"e": str(request.args["entity_id"])}).all()
    lines = [{"product_code": r[0], "product_name": r[1], "location": r[2],
              "warehouse": r[3], "qty": r[4], "avg_cost": r[5], "value": round(r[6], 3)}
             for r in rows]
    return jsonify({"data": {"lines": lines,
                             "total_value": round(sum(l["value"] for l in lines), 3)}})


@bp.get("/assets")
@jwt_required()
def assets_report():
    denied = _deny()
    if denied:
        return denied
    from ...models.asset import Asset
    rows = db.session.query(Asset).filter_by(
        entity_id=uuid.UUID(str(request.args["entity_id"])), is_deleted=False
    ).order_by(Asset.code).all()
    lines = [{"code": a.code, "name_ar": a.name_ar, "status": a.status,
              "cost": float(a.acquisition_cost),
              "accum": float(a.accumulated_depreciation),
              "net": float(a.acquisition_cost) - float(a.accumulated_depreciation)}
             for a in rows]
    return jsonify({"data": {"lines": lines,
                             "total_net": round(sum(l["net"] for l in lines), 3)}})


@bp.get("/tax")
@jwt_required()
def tax_report():
    denied = _deny()
    if denied:
        return denied
    from sqlalchemy import text as _text
    e = str(request.args["entity_id"])
    out_vat = db.session.execute(_text(
        "SELECT COALESCE(SUM(tax_total),0)::float, COUNT(*) FROM customer_invoices "
        "WHERE entity_id = :e AND is_deleted = FALSE AND status = 'posted'"), {"e": e}).first()
    in_vat = db.session.execute(_text(
        "SELECT COALESCE(SUM(tax_total),0)::float, COUNT(*) FROM vendor_bills "
        "WHERE entity_id = :e AND is_deleted = FALSE AND status = 'posted'"), {"e": e}).first()
    return jsonify({"data": {
        "output_vat": out_vat[0], "sales_invoices": out_vat[1],
        "input_vat": in_vat[0], "purchase_bills": in_vat[1],
        "net_payable": round(out_vat[0] - in_vat[0], 3)}})


@bp.get("/budget")
@jwt_required()
def budget_report():
    denied = _deny()
    if denied:
        return denied
    from ...models.project import Budget, BudgetLine
    from ...models.account import Account
    from sqlalchemy import text as _text
    fy_id = request.args.get("fiscal_year_id")
    q = db.session.query(Budget).filter_by(
        entity_id=uuid.UUID(str(request.args["entity_id"])), is_deleted=False)
    if fy_id:
        q = q.filter_by(fiscal_year_id=uuid.UUID(str(fy_id)))
    budgets = q.order_by(Budget.code).all()
    if not budgets:
        return jsonify({"data": {"lines": [], "total_planned": 0, "total_actual": 0}})
    b = budgets[0]
    flines = db.session.query(BudgetLine).filter_by(budget_id=b.id, is_deleted=False).all()
    fy = None
    if b.fiscal_year_id:
        from ...models.entity import FiscalYear
        fy = db.session.get(FiscalYear, b.fiscal_year_id)
    lines = []
    for bl in flines:
        acc = db.session.get(Account, bl.account_id)
        actual = 0.0
        if fy is not None:
            actual = db.session.execute(_text(
                "SELECT COALESCE(SUM(l.debit - l.credit),0)::float FROM journal_lines l "
                "JOIN journal_entries e ON e.id = l.entry_id "
                "WHERE l.account_id = :a AND e.status = 'posted' AND e.is_deleted = FALSE "
                "AND l.is_deleted = FALSE AND e.posting_date BETWEEN :f AND :t"),
                {"a": str(bl.account_id), "f": fy.starts_on, "t": fy.ends_on}).scalar() or 0.0
        lines.append({"account_code": acc.code if acc else "?",
                      "account_name": acc.name_ar if acc else "?",
                      "planned": float(bl.planned_amount), "actual": round(actual, 3),
                      "variance": round(float(bl.planned_amount) - actual, 3)})
    return jsonify({"data": {"budget": b.code, "lines": lines,
                             "total_planned": round(sum(l["planned"] for l in lines), 3),
                             "total_actual": round(sum(l["actual"] for l in lines), 3)}})
