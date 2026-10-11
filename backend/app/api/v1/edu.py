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
