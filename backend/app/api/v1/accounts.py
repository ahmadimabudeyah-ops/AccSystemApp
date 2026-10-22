"""Accounts API: CRUD + tree + search + balances + diagnostics.

GET    /api/v1/accounts            list (filter/search/paginate)
POST   /api/v1/accounts            create (leveled + validated)
GET    /api/v1/accounts/tree       hierarchy (path-ordered, nested)
GET    /api/v1/accounts/search     matches + ancestor chains
GET    /api/v1/accounts/diagnostics dry-run read-only classification
GET    /api/v1/accounts/<id>       detail (+ ancestors)
PUT    /api/v1/accounts/<id>       partial update (atomic version, guarded)
DELETE /api/v1/accounts/<id>       soft delete (guarded)
GET    /api/v1/accounts/<id>/balance direct|aggregate balances
"""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import text, func
from ...extensions import db
from ...models.account import (
    Account, ACCOUNT_TYPES, CONTROL_TYPES, HIERARCHY_ROLES,
    SUGGESTED_BALANCE,
)
from ...services import chart_service as chart
from ...services.chart_service import ChartError, ChartConflict
from ...services.errors import NotFoundError, BadStateError

bp = Blueprint("accounts", __name__)
PAGE_SIZE = 50


def _deny(perm: str):
    claims = get_jwt()
    allowed = claims.get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: ChartError | ChartConflict):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


def _dump(a: Account) -> dict:
    return {"id": str(a.id), "entity_id": str(a.entity_id), "code": a.code,
            "name_ar": a.name_ar, "name_en": a.name_en,
            "parent_id": str(a.parent_id) if a.parent_id else None,
            "level": a.level, "path": a.path, "is_leaf": a.is_leaf,
            "hierarchy_role": a.hierarchy_role,
            "account_type": a.account_type, "control_type": a.control_type,
            "is_postable": a.is_postable, "normal_balance": a.normal_balance,
            "allow_manual": a.allow_manual, "reconcilable": a.reconcilable,
            "require_partner": a.require_partner,
            "require_dimensions": a.require_dimensions,
            "currency_restriction": a.currency_restriction,
            "is_active": a.is_active, "valid_from": a.valid_from.isoformat() if a.valid_from else None,
            "valid_to": a.valid_to.isoformat() if a.valid_to else None,
            "notes": a.notes,
            "status": a.status, "version": a.version}


def _ancestors(a: Account) -> list[dict]:
    chain = []
    seen = set()
    cur = a.parent_id
    while cur is not None and str(cur) not in seen:
        seen.add(str(cur))
        p = db.session.get(Account, cur)
        if p is None or p.is_deleted:
            break
        chain.append({"id": str(p.id), "code": p.code, "name_ar": p.name_ar,
                      "hierarchy_role": p.hierarchy_role})
        cur = p.parent_id
    return list(reversed(chain))


@bp.get("")
@jwt_required()
def list_accounts():
    q = db.session.query(Account).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    if request.args.get("type"):
        q = q.filter_by(account_type=request.args["type"])
    if request.args.get("normal_balance") in ("debit", "credit"):
        q = q.filter_by(normal_balance=request.args["normal_balance"])
    if request.args.get("status") in ("active", "inactive", "suspended"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("role"):
        if request.args["role"] == "unclassified":
            q = q.filter_by(hierarchy_role=None)
        else:
            q = q.filter_by(hierarchy_role=request.args["role"])
    if request.args.get("parent_id"):
        q = q.filter_by(parent_id=uuid.UUID(str(request.args["parent_id"])))
    if request.args.get("postable") in ("true", "false"):
        q = q.filter_by(is_postable=(request.args["postable"] == "true"))
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((Account.code.like(like)) | (Account.name_ar.like(like)))
    total = q.count()
    page = max(int(request.args.get("page", 1)), 1)
    try:
        size = max(1, min(100, int(request.args.get("page_size", PAGE_SIZE))))
    except (TypeError, ValueError):
        size = PAGE_SIZE
    rows = q.order_by(Account.path, Account.code).offset((page - 1) * size).limit(size).all()
    return jsonify({"data": [_dump(a) for a in rows], "page": page,
                    "page_size": size, "total": total})


@bp.get("/tree")
@jwt_required()
def tree():
    entity_id = request.args.get("entity_id")
    q = db.session.query(Account).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if entity_id:
        q = q.filter_by(entity_id=uuid.UUID(str(entity_id)))
    accounts = q.order_by(Account.path).all()
    nodes = {str(a.id): {**_dump(a), "children": []} for a in accounts}
    roots = []
    for a in accounts:
        node = nodes[str(a.id)]
        if a.parent_id and str(a.parent_id) in nodes:
            nodes[str(a.parent_id)]["children"].append(node)
        else:
            roots.append(node)
    return jsonify({"data": roots, "count": len(accounts)})


@bp.get("/search")
@jwt_required()
def search():
    term = (request.args.get("q") or "").strip()
    if len(term) < 1:
        return jsonify({"error": {"code": "QUERY_REQUIRED"}}), 400
    q = db.session.query(Account).filter_by(tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False)
    if request.args.get("entity_id"):
        q = q.filter_by(entity_id=uuid.UUID(str(request.args["entity_id"])))
    like = f"%{term}%"
    q = q.filter((Account.code.like(like)) | (Account.name_ar.like(like)))
    total = q.count()
    rows = q.order_by(Account.path).limit(50).all()
    return jsonify({"data": [{**_dump(a), "ancestors": _ancestors(a)} for a in rows],
                    "total": total})


@bp.get("/stats")
@jwt_required()
def stats():
    entity_id = request.args.get("entity_id")
    if not entity_id:
        return jsonify({"error": {"code": "ENTITY_REQUIRED"}}), 400
    base = db.session.query(Account).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(entity_id)), is_deleted=False)
    total = base.count()
    by_role = dict(db.session.query(Account.hierarchy_role, func.count())
                   .filter(Account.tenant_id == uuid.UUID(str(g.tenant_id)),
                           Account.entity_id == uuid.UUID(str(entity_id)),
                           Account.is_deleted.is_(False))
                   .group_by(Account.hierarchy_role).all())
    return jsonify({"data": {"total": total,
                             "sections": by_role.get("section", 0),
                             "generals": by_role.get("general", 0),
                             "subsidiaries": by_role.get("subsidiary", 0),
                             "details": by_role.get("detail", 0),
                             "unclassified": by_role.get(None, 0)}})


@bp.post("/bulk-status")
@jwt_required()
def bulk_status():
    """تعطيل/تفعيل جماعي — آمن: الحالة لا تمحو التاريخ. كل سجل يُعالج وحده
    وتُرجع نتيجة لكل عنصر ( bulk delete مرفوض عمدًا: الحذف هيكلي وفردي)."""
    denied = _deny("accounts.update")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    ids = data.get("ids") or []
    if not ids or len(ids) > 200:
        return jsonify({"error": {"code": "BAD_SELECTION",
                                  "message": "اختر حتى 200 حساب"}}), 400
    me = uuid.UUID(str(get_jwt().get("sub")))
    results = []
    for raw in ids:
        try:
            aid = uuid.UUID(str(raw))
        except ValueError:
            results.append({"id": raw, "ok": False, "error": "BAD_ID"})
            continue
        acc = db.session.get(Account, aid)
        if acc is None or acc.is_deleted or str(acc.tenant_id) != str(g.tenant_id):
            results.append({"id": str(raw), "ok": False, "error": "NOT_FOUND"})
            continue
        if "is_active" in data:
            acc.is_active = bool(data["is_active"])
        if "status" in data:
            if data["status"] not in ("active", "inactive", "suspended"):
                results.append({"id": str(aid), "ok": False, "error": "BAD_STATUS"})
                continue
            acc.status = data["status"]
        acc.updated_by = me
        results.append({"id": str(aid), "ok": True})
    db.session.commit()
    return jsonify({"data": {"results": results,
                             "ok": sum(1 for r in results if r["ok"]),
                             "failed": sum(1 for r in results if not r["ok"])}})


@bp.get("/diagnostics")
@jwt_required()
def diagnostics():
    denied = _deny("accounts.create")
    if denied:
        return denied
    entity_id = request.args.get("entity_id")
    if not entity_id:
        return jsonify({"error": {"code": "ENTITY_REQUIRED"}}), 400
    try:
        chart.ensure_entity_access(uuid.UUID(str(entity_id)), g.tenant_id)
        return jsonify({"data": chart.diagnose(tenant_id=g.tenant_id, entity_id=entity_id)})
    except (ChartError, ChartConflict) as exc:
        return _err(exc)


@bp.post("")
@jwt_required()
def create_account():
    denied = _deny("accounts.create")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    try:
        entity_id = uuid.UUID(str(data["entity_id"]))
        chart.ensure_entity_access(entity_id, g.tenant_id)
        raw_code = str(data.get("code") or "").strip()
        code = chart.validate_code(raw_code) if raw_code else None
        name_ar = str(data.get("name_ar", "")).strip()
        if not name_ar:
            raise ChartError("الاسم العربي مطلوب")
        account_type = data.get("account_type")
        if account_type not in ACCOUNT_TYPES:
            raise ChartError("التصنيف غير صالح")
        control_type = data.get("control_type", "general")
        if control_type not in CONTROL_TYPES:
            raise ChartError("الوظيفة الرقابية غير مدعومة")
        normal_balance = data.get("normal_balance") or SUGGESTED_BALANCE[account_type]
        if normal_balance not in ("debit", "credit"):
            raise ChartError("الطبيعة debit أو credit فقط")
        role = data.get("hierarchy_role")
        if role is not None and role not in HIERARCHY_ROLES:
            raise ChartError("المستوى الوظيفي غير صالح")
        parent = None
        if data.get("parent_id"):
            parent = db.session.get(Account, uuid.UUID(str(data["parent_id"])))
            if parent is None or parent.is_deleted:
                raise ChartError("الأب المختار غير موجود")
            chart.lock_parent_row(parent.id)
            parent = db.session.get(Account, parent.id)
        chart.validate_parent(tenant_id=g.tenant_id, entity_id=entity_id,
                              parent=parent, wanted_role=role,
                              account_type=account_type)
        if code is None:
            code = chart.suggest_code(tenant_id=g.tenant_id, entity_id=entity_id,
                                      parent=parent, role=role)
        is_postable = chart.coerce_postable(role, data.get("is_postable"))
        acc = Account(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=entity_id,
                      code=code, name_ar=name_ar, name_en=(data.get("name_en") or None),
                      parent_id=parent.id if parent else None,
                      hierarchy_role=role,
                      account_type=account_type, control_type=control_type,
                      is_postable=is_postable, normal_balance=normal_balance,
                      allow_manual=bool(data.get("allow_manual", True)),
                      reconcilable=bool(data.get("reconcilable", False)),
                      require_partner=bool(data.get("require_partner", False)),
                      require_dimensions=bool(data.get("require_dimensions", False)),
                      currency_restriction=(data.get("currency_restriction") or None),
                      notes=(data.get("notes") or None),
                      status="active", is_active=True,
                      created_by=me, updated_by=me)
        db.session.add(acc)
        db.session.flush()
        chart.rebuild_closure(acc.id)
        chart.refresh_is_leaf({parent.id if parent else None})
        db.session.commit()
    except (ChartError, ChartConflict) as exc:
        db.session.rollback()
        return _err(exc)
    except Exception as exc:
        db.session.rollback()
        msg = str(exc)
        if "uq_accounts_code" in msg:
            return jsonify({"error": {"code": "CODE_EXISTS",
                                      "message": "الرمز مستخدم في هذه الشركة"}}), 409
        if "uq_accounts_sibling" in msg:
            return jsonify({"error": {"code": "NAME_EXISTS",
                                      "message": "الاسم مستخدم بين الأشقاء"}}), 409
        if "CIRCULAR" in msg or "PARENT_OTHER" in msg:
            return jsonify({"error": {"code": "CHART_CONFLICT", "message": msg}}), 409
        raise
    return jsonify({"data": _dump(acc)}), 201


@bp.get("/<uuid:acc_id>")
@jwt_required()
def get_account(acc_id):
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted or str(acc.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {**_dump(acc), "ancestors": _ancestors(acc)}})


@bp.put("/<uuid:acc_id>")
@jwt_required()
def update_account(acc_id):
    denied = _deny("accounts.update")
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    me = uuid.UUID(str(get_jwt().get("sub")))
    try:
        # قفل الصف + فحص ذري للنسخة (المشغل يرفع version عند الكتابة،
        # فالقفل المتسلسل يمنع lost update: الثاني يرى النسخة الجديدة ويرفض).
        acc = db.session.execute(
            text("SELECT id FROM accounts WHERE id = :i AND is_deleted = FALSE FOR UPDATE"),
            {"i": str(acc_id)}).first()
        if acc is None:
            return jsonify({"error": {"code": "NOT_FOUND"}}), 404
        a = db.session.get(Account, acc_id)
        if str(a.tenant_id) != str(g.tenant_id):
            return jsonify({"error": {"code": "NOT_FOUND"}}), 404
        if "version" not in data:
            return jsonify({"error": {"code": "VERSION_REQUIRED",
                                      "message": "أعد تحميل الحساب — النسخة مطلوبة لمنع الفقد"}}), 422
        if str(data["version"]) != str(a.version):
            return jsonify({"error": {"code": "CONCURRENT_MODIFICATION",
                                      "message": "تعديل متزامن — أعد تحميل الحساب"}}), 409
        used_lines = chart.account_use_count(a.id)
        has_children = db.session.execute(text(
            "SELECT 1 FROM accounts WHERE parent_id = :i AND is_deleted = FALSE LIMIT 1"),
            {"i": str(a.id)}).first() is not None
        used = used_lines > 0 or has_children
        structural = False

        # --- الاسم والملاحظات: مسموحة دائمًا ---
        if "name_ar" in data:
            v = str(data["name_ar"] or "").strip()
            if not v:
                raise ChartError("الاسم العربي مطلوب")
            a.name_ar = v
        if "name_en" in data:  # null = إفراغ مسموح
            a.name_en = (str(data["name_en"]).strip() or None) if data["name_en"] is not None else None
        if "notes" in data:
            a.notes = data["notes"] if data["notes"] is not None else None

        # --- الحالة والسريان: مسموحة (التعطيل لا يمحو الحركات) ---
        if "status" in data:
            if data["status"] not in ("active", "inactive", "suspended"):
                raise ChartError("الحالة غير صالحة")
            a.status = data["status"]
        if "is_active" in data:
            a.is_active = bool(data["is_active"])
        if "valid_to" in data:
            a.valid_to = date.fromisoformat(data["valid_to"]) if data["valid_to"] else None

        # --- الخصائص التشغيلية: مسموحة للحساب غير المستخدم فقط ---
        for f in ("allow_manual", "reconcilable", "require_partner",
                  "require_dimensions", "control_type"):
            if f in data:
                if used and f in ("control_type",):
                    raise ChartConflict(
                        "لا يمكن تغيير الوظيفة الرقابية لحساب مستخدم — سجل مواءمة صريحة")
                if f == "control_type" and data[f] not in CONTROL_TYPES:
                    raise ChartError("الوظيفة الرقابية غير مدعومة")
                setattr(a, f, data[f] if f == "control_type" else bool(data[f]))
        if "currency_restriction" in data:
            a.currency_restriction = data["currency_restriction"] or None

        # --- الهيكل (مقفل للحساب المستخدم) ---
        if "code" in data and str(data["code"]) != a.code:
            new_code = chart.validate_code(data["code"])
            refs = chart.dynamic_code_refs(a)
            if refs:
                raise ChartConflict("تغيير الرمز مرفوض: " + "؛ ".join(refs))
            if used_lines or has_children:
                raise ChartConflict(
                    "تغيير رمز حساب له حركات/أبناء يتطلب مسار مواءمة معتمد")
            a.code = new_code
            structural = True
        for f in ("account_type", "normal_balance", "hierarchy_role", "is_postable"):
            if f in data and data[f] != getattr(a, f):
                if f == "hierarchy_role":
                    # مواءمة صريحة: مسموحة لفرع بلا حركات (الأبناء وحدهم لا يمنعون)؛
                    # الفرع المستخدم (حركات في أي نسل) مقفل دون مسار مواءمة معتمد.
                    if chart.subtree_has_lines(a.id):
                        raise ChartConflict(
                            "لا يمكن تغيير المستوى لفرع له حركات دون مواءمة صريحة")
                elif used:
                    raise ChartConflict(
                        f"لا يمكن تغيير {f} لحساب مستخدم (حركات/أبناء) دون مواءمة صريحة")
                if f == "account_type" and data[f] not in ACCOUNT_TYPES:
                    raise ChartError("التصنيف غير صالح")
                if f == "normal_balance" and data[f] not in ("debit", "credit"):
                    raise ChartError("الطبيعة debit أو credit فقط")
                if f == "hierarchy_role" and data[f] is not None and data[f] not in HIERARCHY_ROLES:
                    raise ChartError("المستوى الوظيفي غير صالح")
                setattr(a, f, data[f])
                structural = True
        if structural:
            # إعادة اشتقاق التماسك بعد أي تغيير هيكلي. قابلية الترحيل تُشتق من
            # الدور حتمًا، إلا إذا أرسل العميل is_postable صراحة في هذا الطلب
            # فيُتحقق من عدم تناقضه (القيمة المخزنة القديمة ليست تصريحًا).
            parent = db.session.get(Account, a.parent_id) if a.parent_id else None
            chart.validate_parent(tenant_id=a.tenant_id, entity_id=a.entity_id,
                                  parent=parent, wanted_role=a.hierarchy_role,
                                  account_type=a.account_type, self_id=a.id)
            a.is_postable = chart.coerce_postable(
                a.hierarchy_role,
                data.get("is_postable") if "is_postable" in data else None)
            chart.refresh_is_leaf({a.parent_id})
        if "parent_id" in data:
            new_pid = uuid.UUID(str(data["parent_id"])) if data["parent_id"] else None
            if new_pid != a.parent_id:
                if chart.subtree_has_lines(a.id):
                    raise ChartConflict(
                        "نقل فرع له حركات يتطلب مسار مواءمة معتمد — مرفوض هنا")
                new_parent = db.session.get(Account, new_pid) if new_pid else None
                if new_pid and (new_parent is None or new_parent.is_deleted):
                    raise ChartError("الأب الجديد غير موجود")
                old_pid = a.parent_id
                if new_parent is not None:
                    chart.lock_parent_row(new_parent.id)
                chart.validate_parent(tenant_id=a.tenant_id, entity_id=a.entity_id,
                                      parent=new_parent, wanted_role=a.hierarchy_role,
                                      account_type=a.account_type, self_id=a.id)
                a.parent_id = new_pid
                db.session.flush()
                chart.refresh_subtree_paths(a)
                chart.rebuild_closure(a.id)
                chart.refresh_is_leaf({old_pid, new_pid})
        a.updated_by = me
        db.session.commit()
    except (ChartError, ChartConflict) as exc:
        db.session.rollback()
        return _err(exc)
    except Exception as exc:
        db.session.rollback()
        msg = str(exc)
        if "uq_accounts_code" in msg:
            return jsonify({"error": {"code": "CODE_EXISTS",
                                      "message": "الرمز مستخدم في هذه الشركة"}}), 409
        if "uq_accounts_sibling" in msg:
            return jsonify({"error": {"code": "NAME_EXISTS",
                                      "message": "الاسم مستخدم بين الأشقاء"}}), 409
        raise
    return jsonify({"data": _dump(a)})


@bp.delete("/<uuid:acc_id>")
@jwt_required()
def delete_account(acc_id):
    denied = _deny("accounts.delete")
    if denied:
        return denied
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted or str(acc.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    kids = db.session.execute(text(
        "SELECT count(*) FROM accounts WHERE parent_id = :i AND is_deleted = FALSE"),
        {"i": str(acc.id)}).scalar()
    if kids:
        return jsonify({"error": {"code": "HAS_CHILDREN",
                                  "message": "للحساب أبناء غير محذوفين — عطّله بدل حذفه"}}), 409
    if chart.account_use_count(acc.id):
        return jsonify({"error": {"code": "ACCOUNT_HAS_MOVEMENTS",
                                  "message": "للحساب حركات — عطّله بدل حذفه"}}), 409
    refs = chart.dynamic_code_refs(acc)
    if refs:
        return jsonify({"error": {"code": "REFERENCED",
                                  "message": "الحساب مرجعي: " + "؛ ".join(refs)}}), 409
    budgeted = db.session.execute(text(
        "SELECT 1 FROM budget_lines bl JOIN budgets b ON b.id = bl.budget_id "
        "WHERE bl.account_id = :i AND bl.is_deleted = FALSE AND b.is_deleted = FALSE LIMIT 1"),
        {"i": str(acc.id)}).first()
    if budgeted:
        return jsonify({"error": {"code": "REFERENCED",
                                  "message": "الحساب مستخدم في موازنة — عطّله بدل حذفه"}}), 409
    pid = acc.parent_id
    acc.is_deleted = True
    db.session.flush()
    chart.refresh_is_leaf({pid})
    db.session.commit()
    return jsonify({"data": {"id": str(acc.id), "deleted": True}})


@bp.get("/<uuid:acc_id>/balance")
@jwt_required()
def account_balance(acc_id):
    acc = db.session.get(Account, acc_id)
    if acc is None or acc.is_deleted or str(acc.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    from ...services import balance_service as bal
    mode = request.args.get("mode", "direct")
    as_of = request.args.get("as_of")
    if mode not in ("direct", "aggregate"):
        return jsonify({"error": {"code": "BAD_MODE"}}), 400
    data = bal.get_account_balance(acc.id, as_of=as_of, mode=mode)
    return jsonify({"data": data})
