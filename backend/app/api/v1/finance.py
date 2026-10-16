"""Finance API: loans (create/schedule/disburse/repay)."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.addons import Loan, LoanSchedule
from ...services import finance_service
from ...services.errors import AccountingError

bp = Blueprint("finance", __name__)
PAGE = 50


def _deny(perm: str = "treasury.manage"):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


@bp.get("/loans")
@jwt_required()
def list_loans():
    rows = db.session.query(Loan).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Loan.start_on.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(l.id), "code": l.code, "lender": l.lender,
                              "principal": float(l.principal),
                              "annual_rate": float(l.annual_rate),
                              "status": l.status} for l in rows]})


@bp.post("/loans")
@jwt_required()
def create_loan():
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        loan = finance_service.create_loan(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], lender=data["lender"],
            principal=data["principal"], annual_rate=data.get("annual_rate", 0),
            start_on=date.fromisoformat(data["start_on"]) if data.get("start_on") else None,
            months=data["months"], actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(loan.id), "code": loan.code}}), 201


@bp.get("/loans/<uuid:loan_id>")
@jwt_required()
def get_loan(loan_id):
    loan = db.session.get(Loan, loan_id)
    if loan is None or loan.is_deleted or str(loan.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    scheds = db.session.query(LoanSchedule).filter_by(
        loan_id=loan.id, is_deleted=False).order_by(LoanSchedule.period_no).all()
    return jsonify({"data": {"id": str(loan.id), "code": loan.code, "lender": loan.lender,
                             "principal": float(loan.principal),
                             "annual_rate": float(loan.annual_rate),
                             "status": loan.status,
                             "schedule": [{"id": str(s.id), "period_no": s.period_no,
                                           "due_on": s.due_on.isoformat(),
                                           "payment": float(s.payment),
                                           "principal_part": float(s.principal_part),
                                           "interest_part": float(s.interest_part),
                                           "remaining": float(s.remaining),
                                           "status": s.status} for s in scheds]}})


@bp.post("/loans/<uuid:loan_id>/disburse")
@jwt_required()
def disburse_loan(loan_id):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        txn = finance_service.post_disbursement(
            loan_id, cash_account_id=uuid.UUID(str(data["cash_account_id"])),
            liability_code=data.get("liability_code", "2010"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(txn.id), "entry_id": str(txn.journal_entry_id)}}), 201


@bp.post("/loan-schedules/<uuid:sid>/pay")
@jwt_required()
def pay_schedule(sid):
    denied = _deny()
    if denied:
        return denied
    data = request.get_json(force=True)
    try:
        s = finance_service.post_repayment(
            sid, cash_account_id=uuid.UUID(str(data["cash_account_id"])),
            liability_code=data.get("liability_code", "2010"),
            interest_account_code=data.get("interest_account_code", "5160"),
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(s.id), "status": s.status}}), 201
