"""HR API: employees, runs, payslips, loans, leaves."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.hr import Employee, PayrollRun, Payslip, EmployeeLoan, LeaveRequest
from ...services import payroll_service
from ...services.errors import AccountingError

bp = Blueprint("hr", __name__)
PAGE = 50


def _deny(perm: str = "payroll.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


@bp.get("/employees")
@jwt_required()
def list_employees():
    q = db.session.query(Employee).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    rows = q.order_by(Employee.employee_no).limit(PAGE).all()
    return jsonify({"data": [{"id": str(e.id), "employee_no": e.employee_no,
                              "full_name_ar": e.full_name_ar,
                              "gross": float(e.basic_salary) + float(e.housing_allowance)
                              + float(e.transport_allowance) + float(e.other_allowances),
                              "status": e.status} for e in rows]})


@bp.post("/employees")
@jwt_required()
def create_employee():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    e = Employee(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                 party_id=uuid.UUID(str(data["party_id"])) if data.get("party_id") else None,
                 employee_no=data["employee_no"], full_name_ar=data["full_name_ar"],
                 national_id=data.get("national_id"), ss_number=data.get("ss_number"),
                 hire_date=date.fromisoformat(data.get("hire_date", str(date.today()))),
                 basic_salary=data["basic_salary"],
                 housing_allowance=data.get("housing_allowance", 0),
                 transport_allowance=data.get("transport_allowance", 0),
                 other_allowances=data.get("other_allowances", 0),
                 bank_iban=data.get("bank_iban"), created_by=me, updated_by=me)
    db.session.add(e)
    db.session.commit()
    return jsonify({"data": {"id": str(e.id), "employee_no": e.employee_no}}), 201


@bp.get("/employees/<uuid:emp_id>")
@jwt_required()
def get_employee(emp_id):
    e = db.session.get(Employee, emp_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(e.id), "employee_no": e.employee_no,
                             "full_name_ar": e.full_name_ar,
                             "basic_salary": float(e.basic_salary), "status": e.status}})


@bp.post("/employees/<uuid:emp_id>/terminate")
@jwt_required()
def terminate_employee(emp_id):
    denied = _deny()
    if denied:
        return denied
    e = db.session.get(Employee, emp_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from datetime import date as _date
    data = request.get_json(silent=True) or {}
    e.status = "terminated"
    e.end_date = _date.fromisoformat(data["end_date"]) if data.get("end_date") else _date.today()
    db.session.commit()
    return jsonify({"data": {"id": str(e.id), "status": e.status}})


@bp.get("/payroll-runs")
@jwt_required()
def list_runs():
    rows = db.session.query(PayrollRun).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(PayrollRun.pay_month.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "run_code": r.run_code,
                              "pay_month": r.pay_month.isoformat(),
                              "total_net": float(r.total_net),
                              "status": r.status} for r in rows]})


@bp.post("/payroll-runs")
@jwt_required()
def create_run():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        run = payroll_service.create_run(
            tenant_id=g.tenant_id, entity_id=data["entity_id"],
            fiscal_period_id=data["fiscal_period_id"],
            pay_month=date.fromisoformat(data["pay_month"]),
            employee_ids=data.get("employee_ids"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(run.id), "run_code": run.run_code,
                             "total_net": float(run.total_net)}}), 201


@bp.get("/payroll-runs/<uuid:run_id>")
@jwt_required()
def run_detail(run_id):
    run = db.session.get(PayrollRun, run_id)
    if run is None or run.is_deleted or str(run.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    slips = db.session.query(Payslip).filter_by(run_id=run.id, is_deleted=False).all()
    out = []
    for s in slips:
        emp = db.session.get(Employee, s.employee_id)
        out.append({"id": str(s.id), "employee": emp.full_name_ar if emp else "?",
                    "gross": float(s.gross), "deductions": float(s.ss_employee)
                    + float(s.income_tax) + float(s.deductions),
                    "net": float(s.net), "status": s.status})
    return jsonify({"data": {"id": str(run.id), "run_code": run.run_code,
                             "status": run.status, "total_net": float(run.total_net),
                             "payslips": out}})


@bp.post("/payroll-runs/<uuid:run_id>/post")
@jwt_required()
def post_run(run_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        run = payroll_service.post_run(
            run_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))),
            salary_expense_code=data.get("salary_expense_code", "5110"),
            ss_expense_code=data.get("ss_expense_code", "5111"),
            salaries_payable_code=data.get("salaries_payable_code", "2150"),
            ss_payable_code=data.get("ss_payable_code", "2151"),
            tax_payable_code=data.get("tax_payable_code", "2160"))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(run.id), "status": run.status,
                             "entry_id": str(run.journal_entry_id)}})


@bp.get("/loans")
@jwt_required()
def list_loans():
    rows = db.session.query(EmployeeLoan).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(l.id), "employee_id": str(l.employee_id),
                              "amount": float(l.amount), "remaining": float(l.remaining),
                              "status": l.status} for l in rows]})


@bp.post("/loans")
@jwt_required()
def create_loan():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    loan = EmployeeLoan(tenant_id=uuid.UUID(str(g.tenant_id)),
                        employee_id=uuid.UUID(str(data["employee_id"])),
                        amount=data["amount"], installment=data["installment"],
                        remaining=data["amount"], starts_on=date.fromisoformat(data["starts_on"]),
                        created_by=me, updated_by=me)
    db.session.add(loan)
    db.session.commit()
    return jsonify({"data": {"id": str(loan.id)}}), 201


@bp.get("/leaves")
@jwt_required()
def list_leaves():
    rows = db.session.query(LeaveRequest).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(LeaveRequest.from_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(l.id), "employee_id": str(l.employee_id),
                              "leave_type": l.leave_type, "days_count": l.days_count,
                              "status": l.status} for l in rows]})


@bp.post("/leaves")
@jwt_required()
def create_leave():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    frm, to = date.fromisoformat(data["from_date"]), date.fromisoformat(data["to_date"])
    lv = LeaveRequest(tenant_id=uuid.UUID(str(g.tenant_id)),
                      employee_id=uuid.UUID(str(data["employee_id"])),
                      leave_type=data.get("leave_type", "annual"),
                      from_date=frm, to_date=to, days_count=(to - frm).days + 1,
                      reason=data.get("reason"), created_by=me, updated_by=me)
    db.session.add(lv)
    db.session.commit()
    return jsonify({"data": {"id": str(lv.id), "days_count": lv.days_count}}), 201
