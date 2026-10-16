"""Treasury API: boxes, cash movements (auto-draft entries), banks, checks, transfers.

POST /api/v1/treasury/cash-transactions  -> creates txn + DRAFT journal entry
POST /api/v1/treasury/cash-transactions/<id>/post  -> posts linked entry (different user)
Same two-step pattern for transfers.
"""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.treasury import (
    CashBox, CashTransaction, Bank, BankAccount, Check, Transfer,
)
from ...models.journal import Journal
from ...services import posting_service, sequence_service
from ...services.errors import AccountingError

bp = Blueprint("treasury", __name__)
PAGE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


def _journal(entity_id: uuid.UUID, code: str):
    j = db.session.query(Journal).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=entity_id,
        code=code, is_deleted=False).first()
    if j is None:
        raise AccountingError("NO_JOURNAL")
    j.code  # touch
    return j


# ------------------------------------------------------------- boxes

@bp.get("/cash-boxes")
@jwt_required()
def list_boxes():
    rows = db.session.query(CashBox).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(b.id), "entity_id": str(b.entity_id), "code": b.code,
                              "name_ar": b.name_ar, "currency_id": b.currency_id,
                              "is_active": b.is_active} for b in rows]})


@bp.post("/cash-boxes")
@jwt_required()
def create_box():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    b = CashBox(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                branch_id=uuid.UUID(str(data["branch_id"])) if data.get("branch_id") else None,
                code=data["code"], name_ar=data["name_ar"],
                currency_id=data.get("currency_id", "JOD"),
                opening_balance=data.get("opening_balance", 0),
                created_by=me, updated_by=me)
    db.session.add(b)
    db.session.commit()
    return jsonify({"data": {"id": str(b.id), "code": b.code}}), 201


@bp.get("/cash-boxes/<uuid:box_id>")
@jwt_required()
def box_detail(box_id):
    from sqlalchemy import func
    b = db.session.get(CashBox, box_id)
    if b is None or b.is_deleted or str(b.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    ins = db.session.query(func.coalesce(func.sum(CashTransaction.amount), 0)).filter(
        CashTransaction.box_id == b.id, CashTransaction.txn_type == "in",
        CashTransaction.status == "posted", CashTransaction.is_deleted.is_(False)
    ).scalar() or 0
    out = db.session.query(func.coalesce(func.sum(CashTransaction.amount), 0)).filter(
        CashTransaction.box_id == b.id, CashTransaction.txn_type == "out",
        CashTransaction.status == "posted", CashTransaction.is_deleted.is_(False)
    ).scalar() or 0
    balance = float(b.opening_balance) + float(ins) - float(out)
    return jsonify({"data": {"id": str(b.id), "code": b.code, "name_ar": b.name_ar,
                             "opening_balance": float(b.opening_balance),
                             "balance": balance}})


# ------------------------------------------------------------- cash movements

@bp.get("/cash-transactions")
@jwt_required()
def list_cash():
    page = max(int(request.args.get("page", 1)), 1)
    q = db.session.query(CashTransaction).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("box_id"):
        q = q.filter_by(box_id=uuid.UUID(str(request.args["box_id"])))
    rows = q.order_by(CashTransaction.txn_date.desc()).offset((page - 1) * PAGE).limit(PAGE).all()
    return jsonify({"data": [{"id": str(t.id), "doc_number": t.doc_number, "txn_type": t.txn_type,
                              "amount": float(t.amount), "status": t.status,
                              "txn_date": t.txn_date.isoformat()} for t in rows], "page": page})


@bp.post("/cash-transactions")
@jwt_required()
def create_cash():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    entity_id = uuid.UUID(str(data["entity_id"]))
    try:
        journal = _journal(entity_id, "CASH")
        number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id, doctype="cash_txn")
        cash_acc, off_acc = uuid.UUID(str(data["cash_account_id"])), uuid.UUID(str(data["offset_account_id"]))
        debit, credit = (cash_acc, off_acc) if data["txn_type"] == "in" else (off_acc, cash_acc)
        entry = posting_service.create_entry(
            {"tenant_id": tenant_id, "entity_id": entity_id, "journal_id": journal.id,
             "entry_type": "source", "document_date": date.fromisoformat(data.get("txn_date", str(date.today()))),
             "posting_date": date.fromisoformat(data.get("txn_date", str(date.today()))),
             "description": data.get("description"), "source_module": "treasury",
             "source_event_key": data.get("event_key") or f"cash.{number}",
             "currency_id": data.get("currency_id", "JOD")},
            [{"account_id": debit, "debit": data["amount"], "credit": 0},
             {"account_id": credit, "debit": 0, "credit": data["amount"]}],
            actor_id=me)
        txn = CashTransaction(tenant_id=tenant_id, entity_id=entity_id,
                              box_id=uuid.UUID(str(data["box_id"])), doc_number=number,
                              txn_type=data["txn_type"], txn_date=entry.posting_date,
                              amount=data["amount"], currency_id=entry.currency_id,
                              party_id=uuid.UUID(str(data["party_id"])) if data.get("party_id") else None,
                              description=data.get("description"),
                              journal_entry_id=entry.id, event_key=entry.source_event_key,
                              status="draft", created_by=me, updated_by=me)
        db.session.add(txn)
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(txn.id), "doc_number": number,
                             "entry_id": str(entry.id), "status": "draft"}}), 201


@bp.post("/cash-transactions/<uuid:txn_id>/post")
@jwt_required()
def post_cash(txn_id):
    denied = _deny("treasury.manage")
    if denied:
        return denied
    txn = db.session.get(CashTransaction, txn_id)
    if txn is None or txn.is_deleted or str(txn.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    try:
        e = posting_service.post_entry(txn.journal_entry_id, uuid.UUID(str(get_jwt().get("sub"))))
        txn.status = "posted"
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(txn.id), "status": "posted",
                             "official_number": e.official_number}})


# ------------------------------------------------------------- banks & checks

@bp.get("/banks")
@jwt_required()
def list_banks():
    rows = db.session.query(Bank).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(b.id), "code": b.code, "name_ar": b.name_ar} for b in rows]})


@bp.post("/banks")
@jwt_required()
def create_bank():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    b = Bank(tenant_id=uuid.UUID(str(g.tenant_id)), code=data["code"],
             name_ar=data["name_ar"], name_en=data.get("name_en"), created_by=me, updated_by=me)
    db.session.add(b)
    db.session.commit()
    return jsonify({"data": {"id": str(b.id)}}), 201


@bp.get("/bank-accounts")
@jwt_required()
def list_bank_accounts():
    rows = db.session.query(BankAccount).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(a.id), "entity_id": str(a.entity_id), "code": a.code,
                              "iban": a.iban, "currency_id": a.currency_id} for a in rows]})


@bp.post("/bank-accounts")
@jwt_required()
def create_bank_account():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    a = BankAccount(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                    bank_id=uuid.UUID(str(data["bank_id"])), code=data["code"],
                    iban=data.get("iban"), currency_id=data.get("currency_id", "JOD"),
                    opening_balance=data.get("opening_balance", 0),
                    created_by=me, updated_by=me)
    db.session.add(a)
    db.session.commit()
    return jsonify({"data": {"id": str(a.id)}}), 201


@bp.get("/checks")
@jwt_required()
def list_checks():
    rows = db.session.query(Check).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Check.due_on).all()
    return jsonify({"data": [{"id": str(c.id), "check_no": c.check_no, "payee": c.payee,
                              "amount": float(c.amount), "due_on": c.due_on.isoformat(),
                              "status": c.status} for c in rows]})


@bp.post("/checks")
@jwt_required()
def create_check():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    c = Check(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
              bank_account_id=uuid.UUID(str(data["bank_account_id"])),
              check_no=data["check_no"], payee=data["payee"], amount=data["amount"],
              currency_id=data.get("currency_id", "JOD"),
              issue_date=date.fromisoformat(data.get("issue_date", str(date.today()))),
              due_on=date.fromisoformat(data["due_on"]), status="issued",
              created_by=me, updated_by=me)
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


@bp.put("/checks/<uuid:check_id>")
@jwt_required()
def set_check_status(check_id):
    denied = _deny("treasury.manage")
    if denied:
        return denied
    c = db.session.get(Check, check_id)
    if c is None or c.is_deleted or str(c.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    new_status = data.get("status")
    if new_status not in ("issued", "cashed", "bounced", "cancelled", "deferred"):
        return jsonify({"error": {"code": "BAD_STATUS"}}), 422
    me = uuid.UUID(str(get_jwt().get("sub")))
    old_status = c.status
    # قيد GL عند التحصيل أو الرجوع
    if new_status == "cashed" and old_status != "cashed" and c.journal_entry_id is None:
        try:
            from ...models.bank import BankAccount as _BA  # noqa
        except ImportError:
            pass
        from ...models.treasury import BankAccount
        ba = db.session.get(BankAccount, c.bank_account_id)
        if ba is None:
            return jsonify({"error": {"code": "BANK_ACCOUNT_NOT_FOUND"}}), 422
        # حساب البنك من رمز الحساب البنكي
        from ...models.account import Account
        bank_gl = db.session.query(Account).filter_by(
            entity_id=c.entity_id, code=ba.code, is_deleted=False).first()
        if bank_gl is None:
            # بديل: حساب 102001
            bank_gl = db.session.query(Account).filter_by(
                entity_id=c.entity_id, code="102001", is_deleted=False).first()
        # حساب الالتزام (افتراضي 2010 الموردون) أو من الطلب
        offset_code = data.get("offset_account_code", "2010")
        offset_gl = db.session.query(Account).filter_by(
            entity_id=c.entity_id, code=offset_code, is_deleted=False).first()
        if bank_gl is None or offset_gl is None:
            return jsonify({"error": {"code": "ACCOUNT_NOT_CONFIGURED"}}), 422
        journal = _journal(c.entity_id, "BANK")
        entry = posting_service.create_entry(
            {"tenant_id": c.tenant_id, "entity_id": c.entity_id, "journal_id": journal.id,
             "entry_type": "source", "document_date": c.due_on, "posting_date": c.due_on,
             "description": f"تحصيل شيك {c.check_no} — {c.payee}", "source_module": "treasury",
             "source_event_key": f"check.cashed.{c.id}.v1"},
            [{"account_id": offset_gl.id, "debit": float(c.amount), "credit": 0},
             {"account_id": bank_gl.id, "debit": 0, "credit": float(c.amount)}],
            actor_id=me)
        entry = posting_service.post_entry(entry.id, me)
        c.journal_entry_id = entry.id
    elif new_status == "bounced" and old_status == "cashed" and c.journal_entry_id is not None and c.reversal_entry_id is None:
        # عكس قيد التحصيل
        from ...services import reversal_service
        rev = reversal_service.reverse_full(
            c.journal_entry_id, reason=f"شيك مرتد {c.check_no}",
            reversal_date=date.today(), actor_id=me,
            event_key=f"check.bounced.{c.id}.v1")
        c.reversal_entry_id = rev.id
    c.status = new_status
    db.session.commit()
    return jsonify({"data": {"id": str(c.id), "status": c.status}})


# ------------------------------------------------------------- transfers

@bp.get("/transfers")
@jwt_required()
def list_transfers():
    rows = db.session.query(Transfer).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(Transfer.transfer_date.desc()).all()
    return jsonify({"data": [{"id": str(t.id), "doc_number": t.doc_number,
                              "amount": float(t.amount), "status": t.status} for t in rows]})


@bp.post("/transfers")
@jwt_required()
def create_transfer():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    entity_id = uuid.UUID(str(data["entity_id"]))
    try:
        journal = _journal(entity_id, "CASH")
        number = sequence_service.next_doc_number(tenant_id=tenant_id, entity_id=entity_id, doctype="transfer")
        src_acc, dst_acc = uuid.UUID(str(data["from_account_id"])), uuid.UUID(str(data["to_account_id"]))
        entry = posting_service.create_entry(
            {"tenant_id": tenant_id, "entity_id": entity_id, "journal_id": journal.id,
             "entry_type": "source",
             "document_date": date.fromisoformat(data.get("transfer_date", str(date.today()))),
             "posting_date": date.fromisoformat(data.get("transfer_date", str(date.today()))),
             "description": data.get("notes", "تحويل داخلي"), "source_module": "treasury",
             "source_event_key": f"transfer.{number}"},
            [{"account_id": dst_acc, "debit": data["amount"], "credit": 0},
             {"account_id": src_acc, "debit": 0, "credit": data["amount"]}],
            actor_id=me)
        t = Transfer(tenant_id=tenant_id, entity_id=entity_id, doc_number=number,
                     from_box_id=uuid.UUID(str(data["from_box_id"])) if data.get("from_box_id") else None,
                     to_box_id=uuid.UUID(str(data["to_box_id"])) if data.get("to_box_id") else None,
                     from_bank_account_id=uuid.UUID(str(data["from_bank_account_id"])) if data.get("from_bank_account_id") else None,
                     to_bank_account_id=uuid.UUID(str(data["to_bank_account_id"])) if data.get("to_bank_account_id") else None,
                     transfer_date=entry.posting_date, amount=data["amount"],
                     currency_id=entry.currency_id, status="draft",
                     journal_entry_id=entry.id,
                     created_by=me, updated_by=me)
        db.session.add(t)
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(t.id), "doc_number": number,
                             "entry_id": str(entry.id), "status": "draft"}}), 201


@bp.post("/transfers/<uuid:transfer_id>/post")
@jwt_required()
def post_transfer(transfer_id):
    """ترحيل التحويل: قيد مخزن يُرحَّل (خطوتان: إنشاء ثم ترحيل)."""
    denied = _deny("treasury.manage")
    if denied:
        return denied
    t = db.session.get(Transfer, transfer_id)
    if t is None or t.is_deleted or str(t.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if t.status == "posted":
        return jsonify({"data": {"id": str(t.id), "status": "posted"}})
    try:
        e = posting_service.post_entry(t.journal_entry_id, uuid.UUID(str(get_jwt().get("sub"))))
        t.status = "posted"
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(t.id), "status": "posted",
                             "official_number": e.official_number}})


@bp.post("/bank-statements/import")
@jwt_required()
def import_statement():
    """استيراد كشف CSV (أعمدة: date,description,amount) ثم مطابقته آليًا."""
    denied = _deny("treasury.manage")
    if denied:
        return denied
    import csv
    from ...models.ops import BankStatement, BankStatementLine
    from ...services import ops_service
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    tenant_id = uuid.UUID(str(g.tenant_id))
    st = BankStatement(tenant_id=tenant_id,
                       bank_account_id=uuid.UUID(str(data["bank_account_id"])),
                       stmt_date=date.fromisoformat(data.get("stmt_date", str(date.today()))),
                       source_filename=data.get("filename", "upload.csv"),
                       created_by=me, updated_by=me)
    db.session.add(st)
    db.session.flush()
    for row in data["lines"]:
        db.session.add(BankStatementLine(
            tenant_id=tenant_id, statement_id=st.id,
            txn_date=date.fromisoformat(row["date"]), description=row["description"],
            amount=row["amount"], created_by=me, updated_by=me))
    db.session.commit()
    result = ops_service.reconcile_statement(st.id, actor_id=me)
    return jsonify({"data": {"id": str(st.id), **result}}), 201


@bp.get("/bank-statements")
@jwt_required()
def list_statements():
    from ...models.ops import BankStatement
    rows = db.session.query(BankStatement).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(BankStatement.stmt_date.desc()).limit(PAGE).all()
    out = []
    for st in rows:
        total = len([l for l in st.lines if not l.is_deleted])
        matched = len([l for l in st.lines if not l.is_deleted and l.is_matched])
        out.append({"id": str(st.id), "stmt_date": st.stmt_date.isoformat(),
                    "lines": total, "matched": matched})
    return jsonify({"data": out})


@bp.post("/bank-statements/<uuid:st_id>/reconcile")
@jwt_required()
def reconcile_statement(st_id):
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...services import ops_service
    try:
        result = ops_service.reconcile_statement(
            st_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": result})


# ------------------------------------------------------------- bank reconciliations

@bp.get("/bank-reconciliations")
@jwt_required()
def list_reconciliations():
    from ...models.addons import BankReconciliation
    rows = db.session.query(BankReconciliation).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(BankReconciliation.reconciled_on.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "matched_count": r.matched_count,
                              "reconciled_on": r.reconciled_on.isoformat(),
                              "status": r.status} for r in rows]})


@bp.get("/bank-reconciliations/<uuid:r_id>")
@jwt_required()
def get_reconciliation(r_id):
    from ...models.addons import BankReconciliation
    r = db.session.get(BankReconciliation, r_id)
    if r is None or r.is_deleted or str(r.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(r.id), "matched_count": r.matched_count,
                             "reconciled_on": r.reconciled_on.isoformat(),
                             "status": r.status,
                             "lines": [{"id": str(l.id),
                                        "statement_line_id": str(l.statement_line_id),
                                        "entry_id": str(l.entry_id) if l.entry_id else None}
                                       for l in r.lines if not l.is_deleted]}})


# ------------------------------------------------------------- check books

@bp.get("/check-books")
@jwt_required()
def list_check_books():
    from ...models.addons import CheckBook
    rows = db.session.query(CheckBook).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(CheckBook.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(c.id), "code": c.code,
                              "start_no": c.start_no, "end_no": c.end_no,
                              "status": c.status} for c in rows]})


@bp.post("/check-books")
@jwt_required()
def create_check_book():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.addons import CheckBook
    data = request.get_json(force=True)
    cb = CheckBook(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        bank_account_id=uuid.UUID(str(data["bank_account_id"])),
        code=data["code"], start_no=data["start_no"], end_no=data["end_no"],
        status="active",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(cb)
    db.session.commit()
    return jsonify({"data": {"id": str(cb.id), "code": cb.code}}), 201


@bp.get("/check-books/<uuid:cb_id>")
@jwt_required()
def get_check_book(cb_id):
    from ...models.addons import CheckBook
    cb = db.session.get(CheckBook, cb_id)
    if cb is None or cb.is_deleted or str(cb.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(cb.id), "code": cb.code,
                             "start_no": cb.start_no, "end_no": cb.end_no,
                             "status": cb.status}})
