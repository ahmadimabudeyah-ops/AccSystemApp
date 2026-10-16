"""Projects/budgets, audit trail, dimensions, fiscal periods APIs."""
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text as _text
from ...extensions import db
from ...models.project import (
    Project, ProjectCost, ProjectRevenue, Budget, BudgetLine, AuditLog,
    Dimension, DimensionValue,
)
from ...models.entity import FiscalYear, FiscalPeriod
from ...services import period_service
from ...services.errors import AccountingError

bp = Blueprint("projects", __name__)
PAGE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


# ------------------------------------------------------------- projects

@bp.get("/projects")
@jwt_required()
def list_projects():
    rows = db.session.query(Project).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    out = []
    for p in rows:
        costs = db.session.query(ProjectCost).filter_by(project_id=p.id, is_deleted=False).all()
        revs = db.session.query(ProjectRevenue).filter_by(project_id=p.id, is_deleted=False).all()
        tc, tr = sum(float(c.amount) for c in costs), sum(float(r.amount) for r in revs)
        out.append({"id": str(p.id), "code": p.code, "name_ar": p.name_ar,
                    "budget_total": float(p.budget_total), "costs": tc, "revenues": tr,
                    "margin": round(tr - tc, 3), "status": p.status})
    return jsonify({"data": out})


@bp.post("/projects")
@jwt_required()
def create_project():
    denied = _deny("projects.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    p = Project(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                code=data["code"], name_ar=data["name_ar"],
                customer_id=uuid.UUID(str(data["customer_id"])) if data.get("customer_id") else None,
                budget_total=data.get("budget_total", 0), created_by=me, updated_by=me)
    db.session.add(p)
    db.session.commit()
    return jsonify({"data": {"id": str(p.id)}}), 201


@bp.get("/projects/<uuid:pid>")
@jwt_required()
def project_detail(pid):
    p = db.session.get(Project, pid)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    costs = db.session.query(ProjectCost).filter_by(project_id=p.id, is_deleted=False).all()
    revs = db.session.query(ProjectRevenue).filter_by(project_id=p.id, is_deleted=False).all()
    tc, tr = sum(float(c.amount) for c in costs), sum(float(r.amount) for r in revs)
    return jsonify({"data": {"id": str(p.id), "code": p.code, "name_ar": p.name_ar,
                             "budget_total": float(p.budget_total),
                             "costs": tc, "revenues": tr, "margin": round(tr - tc, 3),
                             "status": p.status}})


@bp.post("/projects/<uuid:pid>/costs")
@jwt_required()
def add_cost(pid):
    denied = _deny("projects.manage")
    if denied:
        return denied
    p = db.session.get(Project, pid)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    from datetime import date
    c = ProjectCost(tenant_id=p.tenant_id, project_id=p.id,
                    cost_date=date.fromisoformat(data.get("cost_date", str(date.today()))),
                    amount=data["amount"], description=data.get("description"),
                    journal_entry_id=uuid.UUID(str(data["journal_entry_id"])) if data.get("journal_entry_id") else None,
                    created_by=me, updated_by=me)
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


@bp.post("/projects/<uuid:pid>/revenues")
@jwt_required()
def add_revenue(pid):
    denied = _deny("projects.manage")
    if denied:
        return denied
    p = db.session.get(Project, pid)
    if p is None or p.is_deleted or str(p.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    from datetime import date
    r = ProjectRevenue(tenant_id=p.tenant_id, project_id=p.id,
                       revenue_date=date.fromisoformat(data.get("revenue_date", str(date.today()))),
                       amount=data["amount"], description=data.get("description"),
                       created_by=me, updated_by=me)
    db.session.add(r)
    db.session.commit()
    return jsonify({"data": {"id": str(r.id)}}), 201


# ------------------------------------------------------------- budgets

@bp.get("/budgets")
@jwt_required()
def list_budgets():
    rows = db.session.query(Budget).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(b.id), "code": b.code, "name_ar": b.name_ar,
                              "status": b.status} for b in rows]})


@bp.post("/budgets")
@jwt_required()
def create_budget():
    denied = _deny("projects.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    b = Budget(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
               fiscal_year_id=uuid.UUID(str(data["fiscal_year_id"])),
               code=data["code"], name_ar=data["name_ar"], created_by=me, updated_by=me)
    db.session.add(b)
    db.session.flush()
    for line in data.get("lines", []):
        db.session.add(BudgetLine(tenant_id=b.tenant_id, budget_id=b.id,
                                  account_id=uuid.UUID(str(line["account_id"])),
                                  planned_amount=line["planned_amount"],
                                  created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": {"id": str(b.id)}}), 201


@bp.get("/budgets/<uuid:bid>/variance")
@jwt_required()
def budget_variance(bid):
    """موازنة مقابل فعلي (الفعلي من القيود المرحلة في سنة الموازنة)."""
    b = db.session.get(Budget, bid)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    lines = db.session.query(BudgetLine).filter_by(budget_id=b.id, is_deleted=False).all()
    out = []
    for line in lines:
        actual = db.session.execute(_text(
            "SELECT COALESCE(SUM(l.debit - l.credit),0)::float FROM journal_lines l "
            "JOIN journal_entries e ON e.id = l.entry_id "
            "JOIN fiscal_periods p ON p.id = e.fiscal_period_id "
            "WHERE l.account_id = :a AND p.fiscal_year_id = :y AND e.status IN ('posted','reversed') "
            "AND e.is_deleted = FALSE AND l.is_deleted = FALSE"),
            {"a": line.account_id, "y": b.fiscal_year_id}).scalar() or 0.0
        planned = float(line.planned_amount)
        out.append({"account_id": str(line.account_id), "planned": planned,
                    "actual": round(actual, 3), "variance": round(planned - actual, 3)})
    return jsonify({"data": {"budget_id": str(b.id), "lines": out}})


# ------------------------------------------------------------- audit

@bp.get("/audit-logs")
@jwt_required()
def list_audit():
    denied = _deny("audit.view")
    if denied:
        return denied
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(AuditLog).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)))
    if request.args.get("action"):
        q = q.filter_by(action=request.args["action"])
    rows = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * PAGE).limit(PAGE).all()
    return jsonify({"data": [{"id": str(a.id), "actor_id": str(a.actor_id) if a.actor_id else None,
                              "action": a.action, "entity_type": a.entity_type,
                              "entity_id": str(a.entity_id) if a.entity_id else None,
                              "created_at": a.created_at.isoformat() if a.created_at else None}
                             for a in rows], "page": page})


# ------------------------------------------------------------- dimensions

@bp.get("/dimensions")
@jwt_required()
def list_dimensions():
    rows = db.session.query(Dimension).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    out = []
    for d in rows:
        vals = db.session.query(DimensionValue).filter_by(dimension_id=d.id, is_deleted=False).all()
        out.append({"id": str(d.id), "code": d.code, "name_ar": d.name_ar,
                    "dim_type": d.dim_type, "is_mandatory": d.is_mandatory,
                    "values": [{"id": str(v.id), "code": v.code, "value_ar": v.value_ar} for v in vals]})
    return jsonify({"data": out})


@bp.post("/dimensions")
@jwt_required()
def create_dimension():
    denied = _deny("settings.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    d = Dimension(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                  code=data["code"], name_ar=data["name_ar"], dim_type=data.get("dim_type", "cost_center"),
                  is_mandatory=data.get("is_mandatory", False), created_by=me, updated_by=me)
    db.session.add(d)
    db.session.flush()
    for v in data.get("values", []):
        db.session.add(DimensionValue(tenant_id=d.tenant_id, entity_id=d.entity_id,
                                      dimension_id=d.id, code=v["code"], value_ar=v["value_ar"],
                                      created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": {"id": str(d.id)}}), 201


# ------------------------------------------------------------- fiscal periods

@bp.get("/fiscal-years")
@jwt_required()
def list_years():
    rows = db.session.query(FiscalYear).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(y.id), "entity_id": str(y.entity_id), "code": y.code,
                              "status": y.status} for y in rows]})


@bp.get("/fiscal-periods")
@jwt_required()
def list_periods():
    q = db.session.query(FiscalPeriod).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    rows = q.order_by(FiscalPeriod.starts_on).all()
    return jsonify({"data": [{"id": str(p.id), "code": p.code, "status": p.status,
                              "starts_on": p.starts_on.isoformat(),
                              "ends_on": p.ends_on.isoformat()} for p in rows]})


@bp.post("/fiscal-periods/<uuid:pid>/close")
@jwt_required()
def close_period(pid):
    denied = _deny("period.close")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        p = period_service.lock(pid, hard=data.get("hard", True),
                                actor_id=uuid.UUID(str(get_jwt().get("sub"))),
                                reason=data.get("reason", "close"))
        db.session.commit()
        from ...services import audit_service as _audit_svc
        _audit_svc.record(tenant_id=p.tenant_id, actor_id=get_jwt().get("sub"),
                          action="period_close", entity_type="fiscal_periods", entity_id=p.id,
                          new={"status": p.status})
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(p.id), "status": p.status}})


@bp.post("/fiscal-periods/<uuid:pid>/reopen")
@jwt_required()
def reopen_period(pid):
    denied = _deny("period.close")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        p = period_service.reopen(pid, actor_id=uuid.UUID(str(get_jwt().get("sub"))),
                                  reason=data.get("reason", "reopen with approval"))
        db.session.commit()
    except (AccountingError, ValueError) as exc:
        code = getattr(exc, "code", "VALIDATION_ERROR")
        return jsonify({"error": {"code": code, "message": str(exc)}}), 409
    return jsonify({"data": {"id": str(p.id), "status": p.status}})


@bp.get("/policies")
@jwt_required()
def list_policies():
    rows = db.session.execute(_text(
        "SELECT id::text, entity_id::text, code, framework, status FROM accounting_policies "
        "WHERE tenant_id = :t AND is_deleted = FALSE ORDER BY code"),
        {"t": str(g.tenant_id)}).all()
    return jsonify({"data": [{"id": r[0], "entity_id": r[1], "code": r[2],
                              "framework": r[3], "status": r[4]} for r in rows]})


@bp.get("/aging-receivables")
@jwt_required()
def aging_receivables():
    """أعمار الذمم المدينة بشرائح 0-30/31-60/61-90/+90 من الفواتير المرحلة."""
    from datetime import date as _date
    from ...models.party import Party
    today = _date.today()
    rows = db.session.execute(_text(
        "SELECT i.customer_id::text, i.doc_number, i.due_on, i.remaining_amount::float "
        "FROM customer_invoices i WHERE i.tenant_id = :t AND i.status IN ('posted','partially_paid','overdue') "
        "AND i.remaining_amount > 0 AND i.is_deleted = FALSE ORDER BY i.due_on"),
        {"t": str(g.tenant_id)}).all()
    buckets = {"current": 0.0, "d_1_30": 0.0, "d_31_60": 0.0, "d_61_90": 0.0, "d_over_90": 0.0}
    lines = []
    for cust_id, doc, due, rem in rows:
        age = (today - due).days if due else 0
        key = ("current" if age <= 0 else "d_1_30" if age <= 30 else "d_31_60"
               if age <= 60 else "d_61_90" if age <= 90 else "d_over_90")
        buckets[key] += rem
        cust = db.session.get(Party, cust_id)
        lines.append({"customer": cust.name_ar if cust else "?", "doc_number": doc,
                      "due_on": due.isoformat() if due else None,
                      "remaining": rem, "age_days": age, "bucket": key})
    return jsonify({"data": {"buckets": buckets, "total": round(sum(buckets.values()), 3),
                             "lines": lines}})


@bp.get("/tax-summary")
@jwt_required()
def tax_summary():
    """الالتزام الضريبي: ضريبة محصلة على المبيعات + رصيد حساب الضريبة."""
    vat = db.session.execute(_text(
        "SELECT COALESCE(SUM(t.tax_amount),0)::float FROM customer_invoice_taxes t "
        "JOIN customer_invoices i ON i.id = t.invoice_id "
        "WHERE t.tenant_id = :t AND i.status = 'posted' AND t.is_deleted = FALSE"),
        {"t": str(g.tenant_id)}).scalar() or 0.0
    return jsonify({"data": {"vat_collected_posted": round(vat, 3)}})


# ------------------------------------------------------------- project phases & tasks

@bp.get("/project-phases")
@jwt_required()
def list_phases():
    from ...models.addons import ProjectPhase
    q = db.session.query(ProjectPhase).filter_by(is_deleted=False)
    if request.args.get("project_id"):
        q = q.filter_by(project_id=uuid.UUID(request.args["project_id"]))
    rows = q.order_by(ProjectPhase.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(p.id), "project_id": str(p.project_id),
                              "code": p.code, "name_ar": p.name_ar,
                              "starts_on": p.starts_on.isoformat() if p.starts_on else None,
                              "ends_on": p.ends_on.isoformat() if p.ends_on else None,
                              "status": p.status} for p in rows]})


@bp.post("/project-phases")
@jwt_required()
def create_phase():
    denied = _deny("projects.manage")
    if denied:
        return denied
    from ...models.addons import ProjectPhase
    data = request.get_json(force=True)
    p = ProjectPhase(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        project_id=uuid.UUID(str(data["project_id"])),
        code=data["code"], name_ar=data["name_ar"],
        starts_on=date.fromisoformat(data["starts_on"]) if data.get("starts_on") else None,
        ends_on=date.fromisoformat(data["ends_on"]) if data.get("ends_on") else None,
        status="planned",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(p)
    db.session.commit()
    return jsonify({"data": {"id": str(p.id), "code": p.code}}), 201


@bp.get("/project-tasks")
@jwt_required()
def list_tasks():
    from ...models.addons import ProjectTask
    q = db.session.query(ProjectTask).filter_by(is_deleted=False)
    if request.args.get("phase_id"):
        q = q.filter_by(phase_id=uuid.UUID(request.args["phase_id"]))
    rows = q.order_by(ProjectTask.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(t.id), "phase_id": str(t.phase_id),
                              "code": t.code, "name_ar": t.name_ar,
                              "planned_cost": float(t.planned_cost),
                              "progress_pct": float(t.progress_pct),
                              "status": t.status} for t in rows]})


@bp.post("/project-tasks")
@jwt_required()
def create_task():
    denied = _deny("projects.manage")
    if denied:
        return denied
    from ...models.addons import ProjectTask
    data = request.get_json(force=True)
    t = ProjectTask(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        phase_id=uuid.UUID(str(data["phase_id"])),
        code=data["code"], name_ar=data["name_ar"],
        planned_cost=data.get("planned_cost", 0),
        status="planned",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(t)
    db.session.commit()
    return jsonify({"data": {"id": str(t.id), "code": t.code}}), 201


@bp.patch("/project-tasks/<uuid:task_id>")
@jwt_required()
def update_task(task_id):
    denied = _deny("projects.manage")
    if denied:
        return denied
    from ...models.addons import ProjectTask
    t = db.session.get(ProjectTask, task_id)
    if t is None or t.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    if "progress_pct" in data:
        t.progress_pct = data["progress_pct"]
        if float(t.progress_pct) >= 100:
            t.status = "done"
    if "status" in data:
        t.status = data["status"]
    db.session.commit()
    return jsonify({"data": {"id": str(t.id), "status": t.status,
                             "progress_pct": float(t.progress_pct)}})


# ------------------------------------------------------------- budget versions & transfers

@bp.get("/budgets/<uuid:budget_id>/versions")
@jwt_required()
def list_budget_versions(budget_id):
    from ...models.addons import BudgetVersion
    rows = db.session.query(BudgetVersion).filter_by(
        budget_id=budget_id, is_deleted=False
    ).order_by(BudgetVersion.version_no.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(v.id), "version_no": v.version_no,
                              "notes": v.notes, "status": v.status} for v in rows]})


@bp.post("/budgets/<uuid:budget_id>/versions")
@jwt_required()
def create_budget_version(budget_id):
    denied = _deny("budget.manage")
    if denied:
        return denied
    from ...models.addons import BudgetVersion
    from ...models.project import Budget
    b = db.session.get(Budget, budget_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    last = db.session.query(BudgetVersion).filter_by(
        budget_id=budget_id, is_deleted=False).order_by(
        BudgetVersion.version_no.desc()).first()
    next_no = (last.version_no + 1) if last else 1
    data = request.get_json(force=True, silent=True) or {}
    v = BudgetVersion(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        budget_id=budget_id, version_no=next_no,
        notes=data.get("notes"), status="draft",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(v)
    db.session.commit()
    return jsonify({"data": {"id": str(v.id), "version_no": v.version_no}}), 201


@bp.get("/budget-transfers")
@jwt_required()
def list_budget_transfers():
    from ...models.addons import BudgetTransfer
    rows = db.session.query(BudgetTransfer).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(BudgetTransfer.created_at.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(bt.id), "budget_id": str(bt.budget_id),
                              "amount": float(bt.amount),
                              "reason": bt.reason, "status": bt.status} for bt in rows]})


@bp.post("/budget-transfers")
@jwt_required()
def create_budget_transfer():
    denied = _deny("budget.manage")
    if denied:
        return denied
    from ...models.addons import BudgetTransfer
    data = request.get_json(force=True)
    bt = BudgetTransfer(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        budget_id=uuid.UUID(str(data["budget_id"])),
        from_account_id=uuid.UUID(str(data["from_account_id"])),
        to_account_id=uuid.UUID(str(data["to_account_id"])),
        amount=data["amount"], reason=data.get("reason"), status="draft",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(bt)
    db.session.commit()
    return jsonify({"data": {"id": str(bt.id)}}), 201


@bp.post("/budget-transfers/<uuid:bt_id>/approve")
@jwt_required()
def approve_budget_transfer(bt_id):
    denied = _deny("budget.manage")
    if denied:
        return denied
    from ...models.addons import BudgetTransfer
    from ...models.project import BudgetLine
    bt = db.session.get(BudgetTransfer, bt_id)
    if bt is None or bt.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if bt.status == "approved":
        return jsonify({"data": {"id": str(bt.id), "status": bt.status}})
    if bt.status != "draft":
        return jsonify({"error": {"code": "BAD_STATE",
                                  "message": f"Cannot approve from {bt.status}"}}), 409
    fl = db.session.query(BudgetLine).filter_by(
        budget_id=bt.budget_id, account_id=bt.from_account_id,
        is_deleted=False).first()
    tl = db.session.query(BudgetLine).filter_by(
        budget_id=bt.budget_id, account_id=bt.to_account_id,
        is_deleted=False).first()
    if fl is None or tl is None:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "budget lines missing"}}), 422
    amt = Decimal(str(bt.amount))
    if Decimal(str(fl.amount)) < amt:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "insufficient budget"}}), 422
    fl.amount = float(Decimal(str(fl.amount)) - amt)
    tl.amount = float(Decimal(str(tl.amount)) + amt)
    bt.status = "approved"
    db.session.commit()
    return jsonify({"data": {"id": str(bt.id), "status": bt.status}})


# ------------------------------------------------------------- forecasts

@bp.get("/forecasts")
@jwt_required()
def list_forecasts():
    from ...models.addons import Forecast
    rows = db.session.query(Forecast).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Forecast.created_at.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(f.id), "code": f.code,
                              "name_ar": f.name_ar, "year": f.year,
                              "status": f.status} for f in rows]})


@bp.post("/forecasts")
@jwt_required()
def create_forecast():
    denied = _deny("budget.manage")
    if denied:
        return denied
    from ...models.addons import Forecast, ForecastLine
    data = request.get_json(force=True)
    f = Forecast(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"],
        year=data["year"], status="draft",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(f)
    db.session.flush()
    for l in data.get("lines", []):
        db.session.add(ForecastLine(
            tenant_id=g.tenant_id, forecast_id=f.id,
            account_id=uuid.UUID(str(l["account_id"])),
            month=date.fromisoformat(l["month"]), amount=l["amount"],
            created_by=uuid.UUID(str(get_jwt().get("sub"))),
            updated_by=uuid.UUID(str(get_jwt().get("sub")))))
    db.session.commit()
    return jsonify({"data": {"id": str(f.id), "code": f.code}}), 201


@bp.get("/forecasts/<uuid:fid>")
@jwt_required()
def get_forecast(fid):
    from ...models.addons import Forecast
    f = db.session.get(Forecast, fid)
    if f is None or f.is_deleted or str(f.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(f.id), "code": f.code,
                             "name_ar": f.name_ar, "year": f.year,
                             "status": f.status,
                             "lines": [{"month": l.month.isoformat(),
                                        "account_id": str(l.account_id),
                                        "amount": float(l.amount)}
                                       for l in f.lines if not l.is_deleted]}})


@bp.post("/forecasts/<uuid:fid>/confirm")
@jwt_required()
def confirm_forecast(fid):
    denied = _deny("budget.manage")
    if denied:
        return denied
    from ...models.addons import Forecast
    f = db.session.get(Forecast, fid)
    if f is None or f.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if f.status != "draft":
        return jsonify({"error": {"code": "BAD_STATE",
                                  "message": f"Cannot confirm from {f.status}"}}), 409
    f.status = "confirmed"
    db.session.commit()
    return jsonify({"data": {"id": str(f.id), "status": f.status}})
