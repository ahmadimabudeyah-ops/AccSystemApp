"""HR API: employees, runs, payslips, loans, leaves."""
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
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
            tax_payable_code=data.get("tax_payable_code", "2160"),
            loan_account_code=data.get("loan_account_code"))
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


# ------------------------------------------------------------- employee contracts

@bp.get("/employee-contracts")
@jwt_required()
def list_contracts():
    from ...models.addons import EmployeeContract
    rows = db.session.query(EmployeeContract).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(EmployeeContract.start_on.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(c.id), "employee_id": str(c.employee_id),
                              "start_on": c.start_on.isoformat(),
                              "basic_salary": float(c.basic_salary),
                              "status": c.status} for c in rows]})


@bp.post("/employee-contracts")
@jwt_required()
def create_contract():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import EmployeeContract
    data = request.get_json(force=True)
    c = EmployeeContract(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        employee_id=uuid.UUID(str(data["employee_id"])),
        start_on=date.fromisoformat(data["start_on"]) if data.get("start_on") else date.today(),
        end_on=date.fromisoformat(data["end_on"]) if data.get("end_on") else None,
        basic_salary=data["basic_salary"], status="active",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


# ------------------------------------------------------------- salary structures

@bp.get("/salary-structures")
@jwt_required()
def list_salary_structures():
    from ...models.addons import SalaryStructure
    rows = db.session.query(SalaryStructure).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(SalaryStructure.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(s.id), "code": s.code,
                              "name_ar": s.name_ar, "is_active": s.is_active} for s in rows]})


@bp.post("/salary-structures")
@jwt_required()
def create_salary_structure():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import SalaryStructure, SalaryStructureLine
    data = request.get_json(force=True)
    s = SalaryStructure(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"], is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(s)
    db.session.flush()
    for l in data.get("lines", []):
        db.session.add(SalaryStructureLine(
            tenant_id=g.tenant_id, structure_id=s.id,
            code=l["code"], name_ar=l["name_ar"],
            kind=l.get("kind", "earning"), formula=l.get("formula", "fixed"),
            amount=l.get("amount", 0),
            created_by=uuid.UUID(str(get_jwt().get("sub"))),
            updated_by=uuid.UUID(str(get_jwt().get("sub")))))
    db.session.commit()
    return jsonify({"data": {"id": str(s.id), "code": s.code}}), 201


# ------------------------------------------------------------- leave types & balances

@bp.get("/leave-types")
@jwt_required()
def list_leave_types():
    from ...models.addons import LeaveType
    rows = db.session.query(LeaveType).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(LeaveType.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(lt.id), "code": lt.code,
                              "name_ar": lt.name_ar, "annual_days": lt.annual_days,
                              "is_active": lt.is_active} for lt in rows]})


@bp.post("/leave-types")
@jwt_required()
def create_leave_type():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import LeaveType
    data = request.get_json(force=True)
    lt = LeaveType(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"],
        annual_days=data.get("annual_days", 14), is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(lt)
    db.session.commit()
    return jsonify({"data": {"id": str(lt.id), "code": lt.code}}), 201


@bp.get("/leave-balances")
@jwt_required()
def list_leave_balances():
    from ...models.addons import LeaveBalance
    rows = db.session.query(LeaveBalance).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(LeaveBalance.year.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(lb.id), "employee_id": str(lb.employee_id),
                              "leave_type_id": str(lb.leave_type_id),
                              "year": lb.year, "entitled": float(lb.entitled),
                              "used": float(lb.used)} for lb in rows]})


@bp.post("/leave-balances")
@jwt_required()
def create_leave_balance():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import LeaveBalance
    from ...models.hr import Employee
    data = request.get_json(force=True)
    emp = db.session.get(Employee, uuid.UUID(str(data["employee_id"])))
    if emp is None or emp.is_deleted or str(emp.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    year = int(data["year"])
    exists = db.session.query(LeaveBalance).filter_by(
        employee_id=emp.id, leave_type_id=uuid.UUID(str(data["leave_type_id"])),
        year=year, is_deleted=False).first()
    if exists:
        return jsonify({"error": {"code": "DUPLICATE",
                                  "message": "leave balance already exists"}}), 409
    lb = LeaveBalance(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        employee_id=emp.id,
        leave_type_id=uuid.UUID(str(data["leave_type_id"])),
        year=year, entitled=data.get("entitled", 0), used=data.get("used", 0),
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(lb)
    db.session.commit()
    return jsonify({"data": {"id": str(lb.id), "year": lb.year}}), 201


@bp.get("/leave-balances/<uuid:lb_id>/use")
@jwt_required()
def use_leave_balance(lb_id):
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import LeaveBalance
    lb = db.session.get(LeaveBalance, lb_id)
    if lb is None or lb.is_deleted or str(lb.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    days = float(request.args.get("days", 0))
    if days <= 0:
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "days must be > 0"}}), 422
    from decimal import Decimal
    if Decimal(str(lb.entitled)) - Decimal(str(lb.used)) < Decimal(str(days)):
        return jsonify({"error": {"code": "VALIDATION",
                                  "message": "insufficient balance"}}), 422
    lb.used = float(Decimal(str(lb.used)) + Decimal(str(days)))
    db.session.commit()
    return jsonify({"data": {"id": str(lb.id),
                             "used": float(lb.used),
                             "remaining": float(lb.entitled) - float(lb.used)}})


# ------------------------------------------------------------- attendance

@bp.get("/attendance")
@jwt_required()
def list_attendance():
    from ...models.addons import AttendanceRecord
    rows = db.session.query(AttendanceRecord).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AttendanceRecord.work_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(a.id), "employee_id": str(a.employee_id),
                              "work_date": a.work_date.isoformat(),
                              "status": a.status, "hours": float(a.hours)} for a in rows]})


@bp.post("/attendance")
@jwt_required()
def create_attendance():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import AttendanceRecord
    data = request.get_json(force=True)
    a = AttendanceRecord(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        employee_id=uuid.UUID(str(data["employee_id"])),
        work_date=date.fromisoformat(data["work_date"]) if data.get("work_date") else date.today(),
        status=data.get("status", "present"), hours=data.get("hours", 8),
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(a)
    db.session.commit()
    return jsonify({"data": {"id": str(a.id)}}), 201

# ------------------------------------------------------- income tax brackets
@bp.get("/income-tax-brackets")
@jwt_required()
def list_income_tax_brackets():
    """Jordanian personal income tax slabs — data-driven so a tax review can
    change the numbers without touching code."""
    denied = _deny()
    if denied:
        return denied
    from ...models.hr import IncomeTaxBracket
    year = request.args.get("year", type=int)
    q = db.session.query(IncomeTaxBracket).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if year:
        q = q.filter_by(year=year)
    rows = q.order_by(IncomeTaxBracket.year, IncomeTaxBracket.from_amount).all()
    return jsonify({"data": [{
        "id": str(b.id), "year": b.year,
        "from_amount": float(b.from_amount),
        "to_amount": float(b.to_amount) if b.to_amount else None,
        "rate": float(b.rate), "is_active": b.is_active} for b in rows]})


@bp.post("/income-tax-brackets")
@jwt_required()
def create_income_tax_bracket():
    denied = _deny()
    if denied:
        return denied
    from ...models.hr import IncomeTaxBracket
    me = uuid.UUID(str(get_jwt().get("sub")))
    data = request.get_json(force=True)
    b = IncomeTaxBracket(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        year=int(data["year"]),
        from_amount=Decimal(str(data["from_amount"])),
        to_amount=Decimal(str(data["to_amount"])) if data.get("to_amount") else None,
        rate=Decimal(str(data["rate"])),
        is_active=bool(data.get("is_active", True)),
        created_by=me, updated_by=me)
    db.session.add(b)
    db.session.commit()
    return jsonify({"data": {"id": str(b.id), "year": b.year,
                             "from_amount": float(b.from_amount),
                             "to_amount": float(b.to_amount) if b.to_amount else None,
                             "rate": float(b.rate)}}), 201


@bp.put("/income-tax-brackets/<uuid:bracket_id>")
@jwt_required()
def update_income_tax_bracket(bracket_id):
    denied = _deny()
    if denied:
        return denied
    from ...models.hr import IncomeTaxBracket
    me = uuid.UUID(str(get_jwt().get("sub")))
    b = db.session.get(IncomeTaxBracket, bracket_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    for field in ("year", "from_amount", "to_amount", "rate", "is_active"):
        if field in data:
            v = data[field]
            if field in ("from_amount", "to_amount", "rate"):
                v = Decimal(str(v)) if v is not None else None
            setattr(b, field, v)
    b.updated_by = me
    db.session.commit()
    return jsonify({"data": {"id": str(b.id), "year": b.year,
                             "from_amount": float(b.from_amount),
                             "to_amount": float(b.to_amount) if b.to_amount else None,
                             "rate": float(b.rate)}})


@bp.post("/income-tax-brackets/simulate")
@jwt_required()
def simulate_income_tax():
    """Sanity-check a slab table against payroll_service.annual_tax before a
    client signs off on a tax review."""
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    year = int(data.get("year", 2026))
    amounts = [float(x) for x in data.get("annual_amounts", [])] or [
        9000, 12000, 14000, 19000, 24000, 30000, 40000, 60000]
    out = [{"annual_taxable": a,
            "tax": payroll_service.annual_tax(a, year, g.tenant_id)} for a in amounts]
    return jsonify({"data": {"year": year, "rows": out}})
