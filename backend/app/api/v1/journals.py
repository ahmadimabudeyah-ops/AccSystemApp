"""Journals + entries API.

Journals:  GET/POST /api/v1/journals
Entries:   GET/POST /api/v1/journal-entries
           GET /api/v1/journal-entries/<id>  (+ /lines)
           POST .../<id>/post | /reverse | /approve
           POST .../<id>/comments  |  POST .../<id>/attachments (metadata)
Idempotency-Key header is honoured for POST /journal-entries.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from ...extensions import db
from ...models.journal import (
    Journal, JournalEntry, JournalLine, EntryComment, EntryAttachment, EntryApproval,
)
from ...services import posting_service, approval_service
from ...services.errors import AccountingError, DuplicateEventError

bp = Blueprint("journals", __name__)
PAGE_SIZE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


# ------------------------------------------------------------- journals

@bp.get("/journals")
@jwt_required()
def list_journals():
    rows = db.session.query(Journal).filter_by(tenant_id=g.tenant_id, is_deleted=False).all()
    return jsonify({"data": [{"id": str(j.id), "entity_id": str(j.entity_id), "code": j.code,
                              "name": j.name, "type": j.type, "is_active": j.is_active} for j in rows]})


@bp.post("/journals")
@jwt_required()
def create_journal():
    denied = _deny("journals.create")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt_identity()))
    j = Journal(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
                code=data["code"],
                name=data["name"], type=data.get("type", "general"),
                currency_id=data.get("currency_id", "JOD"),
                default_account_id=uuid.UUID(str(data["default_account_id"])) if data.get("default_account_id") else None,
                sequence_prefix=data.get("sequence_prefix", data["code"]),
                sequence_length=data.get("sequence_length", 6),
                requires_approval=data.get("requires_approval", True),
                allow_manual=data.get("allow_manual", True),
                created_by=me, updated_by=me)
    db.session.add(j)
    db.session.commit()
    return jsonify({"data": {"id": str(j.id), "code": j.code}}), 201


@bp.get("/journals/<uuid:j_id>")
@jwt_required()
def get_journal(j_id):
    j = db.session.get(Journal, j_id)
    if j is None or j.is_deleted or str(j.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(j.id), "entity_id": str(j.entity_id), "code": j.code,
                             "name": j.name, "type": j.type, "is_active": j.is_active,
                             "currency_id": j.currency_id, "default_account_id": str(j.default_account_id) if j.default_account_id else None,
                             "sequence_prefix": j.sequence_prefix, "sequence_length": j.sequence_length,
                             "requires_approval": j.requires_approval, "allow_manual": j.allow_manual}})


@bp.put("/journals/<uuid:j_id>")
@jwt_required()
def update_journal(j_id):
    denied = _deny("journals.create")
    if denied:
        return denied
    j = db.session.get(Journal, j_id)
    if j is None or j.is_deleted or str(j.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt_identity()))
    for field in ("name", "type", "currency_id", "is_active",
                  "requires_approval", "allow_manual"):
        if field in data:
            setattr(j, field, data[field])
    j.updated_by = me
    db.session.commit()
    return jsonify({"data": {"id": str(j.id), "code": j.code, "name": j.name,
                             "type": j.type}})


# ------------------------------------------------------------- entries

def _dump_entry(e: JournalEntry) -> dict:
    return {"id": str(e.id), "entity_id": str(e.entity_id), "journal_id": str(e.journal_id),
            "entry_type": e.entry_type, "document_date": e.document_date.isoformat(),
            "posting_date": e.posting_date.isoformat(), "period_id": str(e.period_id),
            "description": e.description,
            "reference": e.reference, "source_module": e.source_module,
            "currency_id": e.currency_id, "total_debit": float(e.total_debit),
            "total_credit": float(e.total_credit), "status": e.status,
            "official_number": e.official_number, "is_reversed": e.is_reversed,
            "version": e.version}


@bp.get("/journal-entries")
@jwt_required()
def list_entries():
    q = db.session.query(JournalEntry).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    for key in ("entity_id", "journal_id"):
        if request.args.get(key):
            q = q.filter_by(**{key: uuid.UUID(str(request.args[key]))})
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("entry_type"):
        q = q.filter_by(entry_type=request.args["entry_type"])
    if request.args.get("from"):
        q = q.filter(JournalEntry.posting_date >= request.args["from"])
    if request.args.get("to"):
        q = q.filter(JournalEntry.posting_date <= request.args["to"])
    if request.args.get("q"):
        like = f"%{request.args['q'].strip()}%"
        q = q.filter((JournalEntry.official_number.ilike(like))
                     | (JournalEntry.reference.ilike(like))
                     | (JournalEntry.description.ilike(like)))
    total = q.count()
    try:
        size = max(1, min(200, int(request.args.get("page_size", PAGE_SIZE))))
    except (TypeError, ValueError):
        size = PAGE_SIZE
    page = max(int(request.args.get("page", 1)), 1)
    rows = (q.order_by(JournalEntry.posting_date.desc(), JournalEntry.created_at.desc())
            .offset((page - 1) * size).limit(size).all())
    return jsonify({"data": [_dump_entry(e) for e in rows], "page": page,
                    "page_size": size, "total": total})


@bp.post("/journal-entries")
@jwt_required()
def create_entry():
    """إنشاء قيد يدوي: المصدر يُفرض من مسار الخادم (manual).

    أي source_module/entry_type يرسله العميل يُتجاهل — منع تزوير المصدر
    للالتفاف على allow_manual=False أو فصل المهام (صانع ≠ معتمد).
    """
    denied = _deny("journals.post")
    if denied:
        return denied
    data = request.get_json(force=True)
    idem = request.headers.get("Idempotency-Key")
    header = {"tenant_id": uuid.UUID(str(g.tenant_id)), "entity_id": uuid.UUID(str(data["entity_id"])),
                  "journal_id": uuid.UUID(str(data["journal_id"])), "entry_type": "manual",
              "document_date": date.fromisoformat(data["document_date"]),
              "posting_date": date.fromisoformat(data["posting_date"]),
              "description": data.get("description"), "reference": data.get("reference"),
              "source_module": "manual",
              "source_document_id": None,
              "source_event_key": data.get("source_event_key") or idem,
              "currency_id": data.get("currency_id", "JOD"),
              "exchange_rate": data.get("exchange_rate", 1)}
    try:
        entry = posting_service.create_entry(header, data["lines"], actor_id=uuid.UUID(str(get_jwt_identity())))
    except DuplicateEventError as exc:
        return jsonify({"error": {"code": exc.code, "message": str(exc)}}), 200
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump_entry(entry)}), 201


@bp.get("/journal-entries/<uuid:entry_id>")
@jwt_required()
def get_entry(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": _dump_entry(e)})


@bp.get("/journal-entries/<uuid:entry_id>/lines")
@jwt_required()
def entry_lines(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...models.account import Account
    rows = db.session.query(JournalLine).filter_by(entry_id=entry_id, is_deleted=False).order_by(JournalLine.line_number).all()
    acc_ids = {l.account_id for l in rows}
    acc_map = {}
    if acc_ids:
        for a in db.session.query(Account).filter(Account.id.in_(acc_ids)).all():
            if str(a.tenant_id) == str(g.tenant_id):
                acc_map[str(a.id)] = {"code": a.code, "name_ar": a.name_ar, "name_en": a.name_en}
    return jsonify({"data": [{"line_number": l.line_number, "account_id": str(l.account_id),
                               "account_code": (acc_map.get(str(l.account_id)) or {}).get("code"),
                               "account_name": (acc_map.get(str(l.account_id)) or {}).get("name_ar"),
                               "debit": float(l.debit), "credit": float(l.credit),
                               "dimensions": l.dimensions, "description": l.description} for l in rows]})


@bp.post("/journal-entries/<uuid:entry_id>/post")
@jwt_required()
def post_entry(entry_id):
    denied = _deny("journals.post")
    if denied:
        return denied
    try:
        e = posting_service.post_entry(
            entry_id, uuid.UUID(str(get_jwt_identity())),
            allow_self=("admin.*" in get_jwt().get("permissions", [])))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump_entry(e)})


@bp.post("/journal-entries/<uuid:entry_id>/reverse")
@jwt_required()
def reverse_entry(entry_id):
    denied = _deny("journals.reverse")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        reversal_date = date.fromisoformat(
            data.get("reversal_date") or date.today().isoformat())
    except ValueError:
        return jsonify({"error": {"code": "BAD_DATE",
                                  "message": "تاريخ العكس غير صالح"}}), 422
    try:
        rev = posting_service.reverse_entry(entry_id, reason=data.get("reason", ""),
                                            reversal_date=reversal_date,
                                            user_id=uuid.UUID(str(get_jwt_identity())),
                                            event_key=data.get("event_key") or request.headers.get("Idempotency-Key"))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": _dump_entry(rev)}), 201


@bp.post("/journal-entries/<uuid:entry_id>/approve")
@jwt_required()
def approve_entry(entry_id):
    denied = _deny("journals.approve")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    try:
        if data.get("approval_id"):
            row = approval_service.decide(uuid.UUID(str(data["approval_id"])), actor_id=uuid.UUID(str(get_jwt_identity())),
                                          approve=data.get("approve", True), reason=data.get("reason"))
            return jsonify({"data": {"approval_id": str(row.id), "status": row.status}})
        if data.get("approver_id"):
            row = approval_service.request_approval(
                tenant_id=e.tenant_id, entity_id=e.entity_id, entry_id=e.id,
                approver_id=uuid.UUID(str(data["approver_id"])),
                actor_id=uuid.UUID(str(get_jwt_identity())))
            return jsonify({"data": {"approval_id": str(row.id), "status": row.status}}), 201
        # اعتماد مباشر: صلاحية admin.* تسمح باعتماد القيد ذاتيًا (بيئة مستخدم واحد)
        me = uuid.UUID(str(get_jwt_identity()))
        is_admin = "admin.*" in get_jwt().get("permissions", [])
        if e.created_by == me and not is_admin:
            from ...services.errors import SelfApprovalError
            raise SelfApprovalError("لا يمكن اعتماد قيدك بنفسك — يلزم معتمد آخر")
        if e.status not in ("draft", "pending_review"):
            return jsonify({"error": {"code": "BAD_STATE",
                                      "message": f"لا يمكن اعتماد قيد بحالة {e.status}"}}), 409
        e.status = "approved"
        e.approved_by = me
        e.approved_at = datetime.utcnow()
        e.status_changed_at = datetime.utcnow()
        e.status_changed_by = me
        e.updated_by = me
        db.session.commit()
        return jsonify({"data": {"entry_id": str(e.id), "status": e.status}})
    except AccountingError as exc:
        return _err(exc)


@bp.get("/journal-entries/<uuid:entry_id>/approvals")
@jwt_required()
def entry_approvals(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    rows = db.session.query(EntryApproval).filter_by(entry_id=entry_id, is_deleted=False).all()
    return jsonify({"data": [{"id": str(a.id), "approver_id": str(a.approver_id),
                              "status": a.status, "reason": a.reason,
                              "decided_at": a.approved_at.isoformat() if a.approved_at else None}
                             for a in rows]})


@bp.get("/journal-entries/<uuid:entry_id>/comments")
@jwt_required()
def entry_comments(entry_id):
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    rows = db.session.query(EntryComment).filter_by(entry_id=entry_id, is_deleted=False).order_by(EntryComment.commented_at).all()
    return jsonify({"data": [{"id": str(c.id), "comment": c.comment,
                              "commented_by": str(c.commented_by),
                              "commented_at": c.commented_at.isoformat() if c.commented_at else None,
                              "comment_type": c.comment_type} for c in rows]})


@bp.post("/journal-entries/<uuid:entry_id>/comments")
@jwt_required()
def add_comment(entry_id):
    denied = _deny("journals.create")
    if denied:
        return denied
    data = request.get_json(force=True)
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    me = uuid.UUID(str(get_jwt_identity()))
    c = EntryComment(tenant_id=e.tenant_id, entity_id=e.entity_id, entry_id=e.id,
                     comment=data["comment"], commented_by=me,
                     comment_type=data.get("comment_type", "note"),
                     is_internal=data.get("is_internal", True),
                     created_by=me, updated_by=me)
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


@bp.post("/journal-entries/<uuid:entry_id>/attachments")
@jwt_required()
def add_attachment(entry_id):
    denied = _deny("journals.create")
    if denied:
        return denied
    data = request.get_json(force=True)
    e = db.session.get(JournalEntry, entry_id)
    if e is None or e.is_deleted or str(e.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    me = uuid.UUID(str(get_jwt_identity()))
    a = EntryAttachment(tenant_id=e.tenant_id, entity_id=e.entity_id, entry_id=e.id,
                        file_name=data["file_name"], file_type=data["file_type"],
                        file_size=data["file_size"], storage_path=data["storage_path"],
                        file_hash=data["file_hash"], uploaded_by=me,
                        created_by=me, updated_by=me)
    db.session.add(a)
    db.session.commit()
    return jsonify({"data": {"id": str(a.id)}}), 201
