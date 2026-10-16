"""Education API: students, guardians, fee contracts, installments, collection."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.edu import Student, Guardian, FeeContract, FeeInstallment
from ...services import edu_service
from ...services.errors import AccountingError

bp = Blueprint("education", __name__)
PAGE = 50


def _deny(perm: str = "education.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


@bp.get("/students")
@jwt_required()
def list_students():
    q = db.session.query(Student).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    rows = q.order_by(Student.student_no).limit(PAGE).all()
    return jsonify({"data": [{"id": str(s.id), "student_no": s.student_no,
                              "full_name_ar": s.full_name_ar,
                              "grade_level": s.grade_level, "status": s.status} for s in rows]})


@bp.post("/students")
@jwt_required()
def create_student():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    s = Student(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                party_id=uuid.UUID(str(data["party_id"])) if data.get("party_id") else None,
                student_no=data["student_no"], full_name_ar=data["full_name_ar"],
                grade_level=data.get("grade_level"), section_name=data.get("section_name"),
                academic_year=data.get("academic_year", "2026"),
                created_by=me, updated_by=me)
    db.session.add(s)
    db.session.commit()
    return jsonify({"data": {"id": str(s.id)}}), 201


@bp.get("/students/<uuid:sid>")
@jwt_required()
def get_student(sid):
    s = db.session.get(Student, sid)
    if s is None or s.is_deleted or str(s.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(s.id), "code": s.student_no,
                             "student_no": s.student_no, "name_ar": s.full_name_ar,
                             "full_name_ar": s.full_name_ar, "grade_level": s.grade_level,
                             "status": s.status}})


@bp.get("/guardians")
@jwt_required()
def list_guardians():
    rows = db.session.query(Guardian).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).limit(PAGE).all()
    return jsonify({"data": [{"id": str(x.id), "full_name_ar": x.full_name_ar,
                              "phone": x.phone} for x in rows]})


@bp.post("/guardians")
@jwt_required()
def create_guardian():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    x = Guardian(tenant_id=uuid.UUID(str(g.tenant_id)),
                 party_id=uuid.UUID(str(data["party_id"])) if data.get("party_id") else None,
                 full_name_ar=data["full_name_ar"], phone=data.get("phone"),
                 email=data.get("email"), created_by=me, updated_by=me)
    db.session.add(x)
    db.session.commit()
    return jsonify({"data": {"id": str(x.id)}}), 201


@bp.get("/fee-contracts")
@jwt_required()
def list_contracts():
    rows = db.session.query(FeeContract).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).limit(PAGE).all()
    out = []
    for c in rows:
        st = db.session.get(Student, c.student_id)
        out.append({"id": str(c.id), "student": st.full_name_ar if st else "?",
                    "academic_year": c.academic_year, "net_fees": float(c.net_fees),
                    "status": c.status})
    return jsonify({"data": out})


@bp.post("/fee-contracts")
@jwt_required()
def create_contract():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        c = edu_service.create_contract(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], student_id=data["student_id"],
            academic_year=data.get("academic_year", "2026"), total_fees=data["total_fees"],
            discount_pct=data.get("discount_pct", 0),
            installments=data.get("installments", 4),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(c.id), "net_fees": float(c.net_fees)}}), 201


@bp.post("/fee-contracts/<uuid:cid>/post")
@jwt_required()
def post_contract(cid):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        c = edu_service.post_contract(
            cid, actor_id=uuid.UUID(str(get_jwt().get("sub"))),
            revenue_account_code=data.get("revenue_account_code", "4020"))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(c.id), "entry_id": str(c.journal_entry_id)}})


@bp.get("/fee-contracts/<uuid:cid>")
@jwt_required()
def contract_detail(cid):
    c = db.session.get(FeeContract, cid)
    if c is None or c.is_deleted or str(c.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    inst = db.session.query(FeeInstallment).filter_by(contract_id=c.id, is_deleted=False).all()
    return jsonify({"data": {"id": str(c.id), "net_fees": float(c.net_fees),
                             "status": c.status,
                             "installments": [{"id": str(i.id), "installment_no": i.installment_no,
                                               "due_on": i.due_on.isoformat(),
                                               "amount": float(i.amount),
                                               "paid_amount": float(i.paid_amount),
                                               "status": i.status} for i in inst]}})


@bp.post("/fee-installments/<uuid:iid>/pay")
@jwt_required()
def pay_installment(iid):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        pay = edu_service.collect(
            installment_id=iid, amount=data["amount"],
            pay_method=data.get("pay_method", "cash"),
            cash_account_code=data.get("cash_account_code", "101001"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(pay.id), "entry_id": str(pay.journal_entry_id)}}), 201


@bp.post("/students/<uuid:sid>/enroll")
@jwt_required()
def enroll_student(sid):
    denied = _deny()
    if denied:
        return denied
    from ...models.edu import Student
    s = db.session.get(Student, sid)
    if s is None or s.is_deleted or str(s.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    s.status = "enrolled"
    db.session.commit()
    return jsonify({"data": {"id": str(s.id), "status": s.status}})


@bp.post("/students/<uuid:sid>/withdraw")
@jwt_required()
def withdraw_student(sid):
    denied = _deny()
    if denied:
        return denied
    from ...models.edu import Student
    s = db.session.get(Student, sid)
    if s is None or s.is_deleted or str(s.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    s.status = "withdrawn"
    db.session.commit()
    return jsonify({"data": {"id": str(s.id), "status": s.status}})


# ------------------------------------------------------------- academic years & terms

@bp.get("/academic-years")
@jwt_required()
def list_academic_years():
    from ...models.addons import AcademicYear
    rows = db.session.query(AcademicYear).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AcademicYear.starts_on.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(ay.id), "code": ay.code,
                              "starts_on": ay.starts_on.isoformat(),
                              "ends_on": ay.ends_on.isoformat(),
                              "status": ay.status} for ay in rows]})


@bp.post("/academic-years")
@jwt_required()
def create_academic_year():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import AcademicYear
    data = request.get_json(force=True)
    ay = AcademicYear(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"],
        starts_on=date.fromisoformat(data["starts_on"]),
        ends_on=date.fromisoformat(data["ends_on"]),
        status="active",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(ay)
    db.session.commit()
    return jsonify({"data": {"id": str(ay.id), "code": ay.code}}), 201


@bp.get("/academic-terms")
@jwt_required()
def list_academic_terms():
    from ...models.addons import AcademicTerm
    rows = db.session.query(AcademicTerm).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AcademicTerm.starts_on.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(at.id), "year_id": str(at.year_id),
                              "code": at.code, "name_ar": at.name_ar,
                              "starts_on": at.starts_on.isoformat(),
                              "ends_on": at.ends_on.isoformat()} for at in rows]})


@bp.post("/academic-terms")
@jwt_required()
def create_academic_term():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import AcademicTerm
    data = request.get_json(force=True)
    at = AcademicTerm(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        year_id=uuid.UUID(str(data["year_id"])),
        code=data["code"], name_ar=data["name_ar"],
        starts_on=date.fromisoformat(data["starts_on"]),
        ends_on=date.fromisoformat(data["ends_on"]),
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(at)
    db.session.commit()
    return jsonify({"data": {"id": str(at.id), "code": at.code}}), 201


# ------------------------------------------------------------- grade levels

@bp.get("/grade-levels")
@jwt_required()
def list_grade_levels():
    from ...models.addons import GradeLevel
    rows = db.session.query(GradeLevel).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(GradeLevel.order_no).limit(PAGE).all()
    return jsonify({"data": [{"id": str(gl.id), "code": gl.code,
                              "name_ar": gl.name_ar, "order_no": gl.order_no} for gl in rows]})


@bp.post("/grade-levels")
@jwt_required()
def create_grade_level():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import GradeLevel
    data = request.get_json(force=True)
    gl = GradeLevel(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"],
        order_no=data.get("order_no", 0),
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(gl)
    db.session.commit()
    return jsonify({"data": {"id": str(gl.id), "code": gl.code}}), 201


# ------------------------------------------------------------- fee structures

@bp.get("/fee-structures")
@jwt_required()
def list_fee_structures():
    from ...models.addons import FeeStructure
    rows = db.session.query(FeeStructure).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(FeeStructure.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(fs.id), "code": fs.code,
                              "name_ar": fs.name_ar, "academic_year": fs.academic_year,
                              "status": fs.status} for fs in rows]})


@bp.post("/fee-structures")
@jwt_required()
def create_fee_structure():
    denied = _deny()
    if denied:
        return denied
    from ...models.addons import FeeStructure, FeeStructureLine
    data = request.get_json(force=True)
    fs = FeeStructure(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"],
        academic_year=data.get("academic_year", str(date.today().year)),
        status="active",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(fs)
    db.session.flush()
    for l in data.get("lines", []):
        db.session.add(FeeStructureLine(
            tenant_id=g.tenant_id, structure_id=fs.id,
            grade_code=l["grade_code"], amount=l["amount"],
            created_by=uuid.UUID(str(get_jwt().get("sub"))),
            updated_by=uuid.UUID(str(get_jwt().get("sub")))))
    db.session.commit()
    return jsonify({"data": {"id": str(fs.id), "code": fs.code}}), 201
