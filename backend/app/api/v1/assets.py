"""Assets + taxes + currencies API."""
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.asset import Asset, AssetCategory
from ...models.account import Account
from ...models.treasury import Currency, Tax
from ...services import posting_service
from ...services.errors import AccountingError, DuplicateEventError

bp = Blueprint("assets", __name__)
PAGE = 50


def _deny(perm: str):
    allowed = get_jwt().get("permissions", [])
    if perm not in allowed and "admin.*" not in allowed:
        return jsonify({"error": {"code": "FORBIDDEN", "message": perm}}), 403
    return None


def _err(exc: AccountingError):
    return jsonify({"error": {"code": exc.code, "message": str(exc)}}), exc.status


@bp.get("/currencies")
@jwt_required()
def list_currencies():
    rows = db.session.query(Currency).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    if not rows:
        rows = [Currency(code=c, name_ar=n) for c, n in
                [("JOD", "دينار أردني"), ("USD", "دولار أمريكي"), ("EUR", "يورو"),
                 ("SAR", "ريال سعودي"), ("AED", "درهم إماراتي")]]
    return jsonify({"data": [{"id": str(r.id) if r.id else r.code, "code": r.code,
                              "name_ar": r.name_ar} for r in rows]})


@bp.get("/taxes")
@jwt_required()
def list_taxes():
    rows = db.session.query(Tax).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(t.id), "entity_id": str(t.entity_id), "code": t.code,
                              "name_ar": t.name_ar, "rate": float(t.rate),
                              "tax_type": t.tax_type, "is_active": t.is_active} for t in rows]})


@bp.post("/taxes")
@jwt_required()
def create_tax():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    t = Tax(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
            code=data["code"], name_ar=data["name_ar"], rate=data["rate"],
            tax_type=data.get("tax_type", "sale"), created_by=me, updated_by=me)
    db.session.add(t)
    db.session.commit()
    return jsonify({"data": {"id": str(t.id)}}), 201


@bp.get("/taxes/<uuid:tax_id>")
@jwt_required()
def get_tax(tax_id):
    t = db.session.get(Tax, tax_id)
    if t is None or t.is_deleted or str(t.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(t.id), "code": t.code, "name_ar": t.name_ar,
                             "rate": float(t.rate), "tax_type": t.tax_type,
                             "is_active": t.is_active, "status": "active"}})


@bp.get("/asset-categories")
@jwt_required()
def list_categories():
    rows = db.session.query(AssetCategory).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(c.id), "code": c.code, "name_ar": c.name_ar,
                              "useful_life_years": c.useful_life_years} for c in rows]})


@bp.post("/asset-categories")
@jwt_required()
def create_category():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    c = AssetCategory(tenant_id=uuid.UUID(str(g.tenant_id)), code=data["code"],
                      name_ar=data["name_ar"],
                      useful_life_years=data.get("useful_life_years", 5),
                      depreciation_method=data.get("depreciation_method", "straight_line"),
                      created_by=me, updated_by=me)
    db.session.add(c)
    db.session.commit()
    return jsonify({"data": {"id": str(c.id)}}), 201


@bp.get("/assets")
@jwt_required()
def list_assets():
    rows = db.session.query(Asset).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(a.id), "entity_id": str(a.entity_id), "code": a.code,
                              "name_ar": a.name_ar, "status": a.status,
                              "net": float(a.acquisition_cost) - float(a.accumulated_depreciation)}
                             for a in rows]})


@bp.post("/assets")
@jwt_required()
def create_asset():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    dup = db.session.query(Asset).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), code=data["code"], is_deleted=False).first()
    if dup is not None:
        return jsonify({"error": {"code": "DUPLICATE_CODE",
                                  "message": f"Asset code already exists: {data['code']}"}}), 409
    a = Asset(tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=uuid.UUID(str(data["entity_id"])),
              category_id=uuid.UUID(str(data["category_id"])), code=data["code"],
              name_ar=data["name_ar"],
              acquisition_date=date.fromisoformat(data["acquisition_date"]),
              acquisition_cost=data["acquisition_cost"],
              residual_value=data.get("residual_value", 0),
              location_text=data.get("location_text"), created_by=me, updated_by=me)
    db.session.add(a)
    db.session.commit()
    return jsonify({"data": {"id": str(a.id)}}), 201


@bp.get("/assets/<uuid:asset_id>")
@jwt_required()
def asset_detail(asset_id):
    a = db.session.get(Asset, asset_id)
    if a is None or a.is_deleted or str(a.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    return jsonify({"data": {"id": str(a.id), "code": a.code, "name_ar": a.name_ar,
                             "category_id": str(a.category_id) if a.category_id else None,
                             "acquisition_date": a.acquisition_date.isoformat() if a.acquisition_date else None,
                             "acquisition_cost": float(a.acquisition_cost),
                             "residual_value": float(a.residual_value or 0),
                             "location_text": a.location_text,
                             "accumulated_depreciation": float(a.accumulated_depreciation),
                             "net": float(a.acquisition_cost) - float(a.accumulated_depreciation),
                             "status": a.status}})


@bp.put("/assets/<uuid:asset_id>")
@jwt_required()
def update_asset(asset_id):
    denied = _deny("treasury.manage")
    if denied:
        return denied
    a = db.session.get(Asset, asset_id)
    if a is None or a.is_deleted or str(a.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    if data.get("category_id"):
        a.category_id = uuid.UUID(str(data["category_id"]))
    if data.get("code"):
        dup = db.session.query(Asset).filter(
            Asset.tenant_id == uuid.UUID(str(g.tenant_id)),
            Asset.code == data["code"], Asset.id != a.id,
            Asset.is_deleted.is_(False)).first()
        if dup is not None:
            return jsonify({"error": {"code": "DUPLICATE_CODE",
                                      "message": f"Asset code already exists: {data['code']}"}}), 409
        a.code = data["code"]
    if data.get("name_ar"):
        a.name_ar = data["name_ar"]
    if data.get("acquisition_date"):
        a.acquisition_date = date.fromisoformat(data["acquisition_date"])
    if data.get("acquisition_cost") is not None:
        a.acquisition_cost = data["acquisition_cost"]
    if data.get("residual_value") is not None:
        a.residual_value = data["residual_value"]
    if "location_text" in data:
        a.location_text = data.get("location_text")
    a.updated_by = me
    db.session.commit()
    return jsonify({"data": {"id": str(a.id), "code": a.code, "name_ar": a.name_ar}})


@bp.post("/assets/depreciate-run")
@jwt_required()
def depreciate_run():
    """إهلاك جماعي شهري: يرحّل قسطًا لكل أصل نشط (يتجاوز المرحّل/المستبعد، idempotent لكل أصل+تاريخ)."""
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    entity_id = uuid.UUID(str(data["entity_id"]))
    posting_date = data.get("posting_date", str(date.today()))
    exp_acc = uuid.UUID(str(data["expense_account_id"]))
    acc_acc = uuid.UUID(str(data["accum_account_id"]))
    # تقييد حسابات الإهلاك: مصروف 5130 + مجمع 1519
    from ...models.account import Account as _Acct
    _exp = db.session.get(_Acct, exp_acc)
    _acc = db.session.get(_Acct, acc_acc)
    if _exp is None or _exp.code != "5130":
        return jsonify({"error": {"code": "BAD_DEPR_ACCOUNT",
                                  "message": "expense_account_id must be account 5130 (Depreciation)"}}), 422
    if _acc is None or _acc.code != "1519":
        return jsonify({"error": {"code": "BAD_DEPR_ACCOUNT",
                                  "message": "accum_account_id must be account 1519 (Accumulated depreciation)"}}), 422
    from ...models.journal import Journal as _J
    journal = db.session.query(_J).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=entity_id,
        code="GEN", is_deleted=False).first()
    if journal is None:
        return jsonify({"error": {"code": "NOT_CONFIGURED", "message": "Journal GEN missing"}}), 409
    assets = db.session.query(Asset).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=entity_id,
        is_deleted=False, status="active").all()
    from ...services import event_service
    done, skipped, failed = [], [], []
    for a in assets:
        # فحص مسبق: الخدمات الداخلية تُتمم المعاملة (commit) فلا تُستخدم savepoints هنا؛
        # كل أصل يُرحّل ويُحفظ مستقلًا، والفشل يتراجع عن الأصل الحالي فقط.
        key = f"asset.depr.{a.id}.{posting_date}"
        try:
            if event_service.get_by_key(tenant_id=a.tenant_id, entity_id=a.entity_id, event_key=key):
                skipped.append({"asset_id": str(a.id), "code": a.code, "reason": "ALREADY_RUN"})
                continue
            cat = db.session.get(AssetCategory, a.category_id)
            months = (cat.useful_life_years if cat else 5) * 12
            book = float(a.acquisition_cost) - float(a.accumulated_depreciation) - float(a.residual_value)
            method = data.get("method", (cat.depreciation_method if cat else "straight_line"))
            if method == "declining":
                amount = round(max(0.0, book) * round(2 / months, 6), 3)
            else:
                amount = round((float(a.acquisition_cost) - float(a.residual_value)) / months, 3)
            amount = min(amount, round(max(0.0, book), 3))
            if amount <= 0:
                skipped.append({"asset_id": str(a.id), "code": a.code, "reason": "FULLY_DEPRECIATED"})
                continue
            entry = posting_service.create_entry(
                {"tenant_id": a.tenant_id, "entity_id": a.entity_id, "journal_id": journal.id,
                 "entry_type": "depreciation",
                 "document_date": date.fromisoformat(posting_date),
                 "posting_date": date.fromisoformat(posting_date),
                 "description": f"إهلاك {a.code}", "source_module": "assets",
                 "source_document_id": a.id, "source_event_key": key},
                [{"account_id": exp_acc, "debit": amount, "credit": 0},
                 {"account_id": acc_acc, "debit": 0, "credit": amount}],
                actor_id=me)
            entry = posting_service.post_entry(entry.id, me)
            a.accumulated_depreciation = float(a.accumulated_depreciation) + amount
            if a.accumulated_depreciation >= float(a.acquisition_cost) - float(a.residual_value) - 0.001:
                a.status = "fully_depreciated"
            db.session.commit()
            done.append({"asset_id": str(a.id), "code": a.code, "amount": amount})
        except DuplicateEventError:
            db.session.rollback()
            skipped.append({"asset_id": str(a.id), "code": a.code, "reason": "ALREADY_RUN"})
        except AccountingError as exc:
            db.session.rollback()
            failed.append({"asset_id": str(a.id), "code": a.code, "reason": exc.code})
    return jsonify({"data": {"posted": done, "skipped": skipped, "failed": failed}}), 201


@bp.post("/assets/<uuid:asset_id>/depreciate")
@jwt_required()
def depreciate(asset_id):
    """ترحيل إهلاك شهر واحد (ثابت أو متناقص) كقيد مرحّل مباشرة (حدث نظامي)."""
    denied = _deny("treasury.manage")
    if denied:
        return denied
    a = db.session.get(Asset, asset_id)
    if a is None or a.is_deleted or str(a.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    cat = db.session.get(AssetCategory, a.category_id)
    months = (cat.useful_life_years if cat else 5) * 12
    book = float(a.acquisition_cost) - float(a.accumulated_depreciation) - float(a.residual_value)
    method = data.get("method", (cat.depreciation_method if cat else "straight_line"))
    if method == "declining":
        rate = data.get("declining_rate", round(2 / months, 6))
        amount = round(max(0.0, book) * rate, 3)
    else:
        amount = round((float(a.acquisition_cost) - float(a.residual_value)) / months, 3)
    remaining = max(0.0, book)
    amount = min(amount, round(remaining, 3))
    if amount <= 0:
        return jsonify({"error": {"code": "FULLY_DEPRECIATED"}}), 409
    # تقييد حسابات الإهلاك: مصروف 5130 + مجمع 1519
    from ...models.account import Account as _Acct2
    _exp2 = db.session.get(_Acct2, uuid.UUID(str(data["expense_account_id"])))
    _acc2 = db.session.get(_Acct2, uuid.UUID(str(data["accum_account_id"])))
    if _exp2 is None or _exp2.code != "5130":
        return jsonify({"error": {"code": "BAD_DEPR_ACCOUNT",
                                  "message": "expense_account_id must be account 5130 (Depreciation)"}}), 422
    if _acc2 is None or _acc2.code != "1519":
        return jsonify({"error": {"code": "BAD_DEPR_ACCOUNT",
                                  "message": "accum_account_id must be account 1519 (Accumulated depreciation)"}}), 422
    try:
        from ...models.journal import Journal
        journal = db.session.query(Journal).filter_by(
            tenant_id=a.tenant_id, entity_id=a.entity_id, code="GEN", is_deleted=False).first()
        if journal is None:
            return jsonify({"error": {"code": "NOT_CONFIGURED", "message": "Journal GEN missing"}}), 409
        entry = posting_service.create_entry(
            {"tenant_id": a.tenant_id, "entity_id": a.entity_id, "journal_id": journal.id,
             "entry_type": "depreciation",
             "document_date": date.fromisoformat(data.get("posting_date", str(date.today()))),
             "posting_date": date.fromisoformat(data.get("posting_date", str(date.today()))),
              "description": f"إهلاك {a.code}", "source_module": "assets",
              "source_document_id": a.id,
              "source_event_key": f"asset.depr.{a.id}.{data.get('posting_date', str(date.today()))}"},
             [{"account_id": uuid.UUID(str(data["expense_account_id"])), "debit": amount, "credit": 0},
              {"account_id": uuid.UUID(str(data["accum_account_id"])), "debit": 0, "credit": amount}],
             actor_id=me)
        entry = posting_service.post_entry(entry.id, me)
        a.accumulated_depreciation = float(a.accumulated_depreciation) + amount
        if a.accumulated_depreciation >= float(a.acquisition_cost) - float(a.residual_value) - 0.001:
            a.status = "fully_depreciated"
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"entry_id": str(entry.id), "amount": amount,
                             "accumulated": float(a.accumulated_depreciation),
                             "status": a.status}}), 201


@bp.post("/assets/<uuid:asset_id>/dispose")
@jwt_required()
def dispose_asset(asset_id):
    """استبعاد أصل: مجمع + مقبوضات مدينة / الأصل بالكلفة دائن + ربح/خسارة."""
    denied = _deny("treasury.manage")
    if denied:
        return denied
    a = db.session.get(Asset, asset_id)
    if a is None or a.is_deleted or str(a.tenant_id) != str(g.tenant_id):
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if a.status == "disposed":
        return jsonify({"error": {"code": "ALREADY_DISPOSED"}}), 409
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    proceeds = float(data.get("proceeds", 0))
    net = float(a.acquisition_cost) - float(a.accumulated_depreciation)
    gain = round(proceeds - net, 3)
    try:
        from ...models.journal import Journal
        journal = db.session.query(Journal).filter_by(
            tenant_id=a.tenant_id, entity_id=a.entity_id, code="GEN", is_deleted=False).first()
        lines = [
            {"account_id": uuid.UUID(str(data["accum_account_id"])),
             "debit": float(a.accumulated_depreciation), "credit": 0},
            {"account_id": uuid.UUID(str(data["asset_account_id"])),
             "debit": 0, "credit": float(a.acquisition_cost)}]
        if proceeds > 0:
            lines.append({"account_id": uuid.UUID(str(data["cash_account_id"])),
                          "debit": proceeds, "credit": 0})
        if gain > 0:
            lines.append({"account_id": uuid.UUID(str(data["gain_account_id"])),
                          "debit": 0, "credit": gain})
        elif gain < 0:
            lines.append({"account_id": uuid.UUID(str(data["loss_account_id"])),
                          "debit": -gain, "credit": 0})
        entry = posting_service.create_entry(
            {"tenant_id": a.tenant_id, "entity_id": a.entity_id, "journal_id": journal.id,
             "entry_type": "adjustment",
             "document_date": date.fromisoformat(data.get("disposal_date", str(date.today()))),
             "posting_date": date.fromisoformat(data.get("disposal_date", str(date.today()))),
             "description": f"استبعاد {a.code}", "source_module": "assets",
             "source_document_id": a.id, "source_event_key": f"asset.dispose.{a.id}.v1"},
            lines, actor_id=me)
        entry = posting_service.post_entry(entry.id, me)
        a.status = "disposed"
        a.is_active = False
        db.session.commit()
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(a.id), "status": a.status, "gain_loss": gain}}), 201


@bp.get("/tax-returns")
@jwt_required()
def list_tax_returns():
    from ...models.ops import TaxReturn
    rows = db.session.query(TaxReturn).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(TaxReturn.period_code.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "period_code": r.period_code,
                              "tax_due": float(r.tax_due),
                              "net_due": float(r.net_due or 0),
                              "status": r.status} for r in rows]})


@bp.post("/tax-returns/file")
@jwt_required()
def file_tax_return():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    data = request.get_json(force=True)
    from ...services import ops_service
    try:
        ret = ops_service.file_tax_return(
            tenant_id=g.tenant_id, entity_id=data["entity_id"], tax_id=data["tax_id"],
            period_code=data["period_code"],
            actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    except AccountingError as exc:
        return _err(exc)
    return jsonify({"data": {"id": str(ret.id), "period_code": ret.period_code,
                             "sales_total": float(ret.sales_total or 0),
                             "purchase_total": float(ret.purchase_total or 0),
                             "output_tax": float(ret.output_tax or 0),
                             "input_tax": float(ret.input_tax or 0),
                             "tax_due": float(ret.tax_due),
                             "net_due": float(ret.net_due or 0),
                             "status": ret.status}}), 201


@bp.get("/recurring-entries")
@jwt_required()
def list_recurring():
    from ...models.ops import RecurringEntry
    rows = db.session.query(RecurringEntry).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False).all()
    return jsonify({"data": [{"id": str(r.id), "code": r.code, "frequency": r.frequency,
                              "next_run_on": r.next_run_on.isoformat(),
                              "is_active": r.is_active} for r in rows]})


@bp.post("/recurring-entries")
@jwt_required()
def create_recurring():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.ops import RecurringEntry
    from datetime import date as _date
    data = request.get_json(force=True)
    me = uuid.UUID(str(get_jwt().get("sub")))
    r = RecurringEntry(tenant_id=uuid.UUID(str(g.tenant_id)),
                       entity_id=uuid.UUID(str(data["entity_id"])),
                       code=data["code"], description=data.get("description", ""),
                       journal_id=uuid.UUID(str(data["journal_id"])),
                       frequency=data.get("frequency", "monthly"),
                       next_run_on=_date.fromisoformat(data["next_run_on"]),
                       template={"lines": data["lines"]},
                       created_by=me, updated_by=me)
    db.session.add(r)
    db.session.commit()
    return jsonify({"data": {"id": str(r.id)}}), 201


@bp.post("/recurring-entries/run-due")
@jwt_required()
def run_recurring():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...services import ops_service
    ran = ops_service.run_due_recurring(
        tenant_id=g.tenant_id, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
    return jsonify({"data": {"ran_entries": ran}})


# ------------------------------------------------------------- asset transfers/disposals/revaluations

@bp.get("/asset-transfers")
@jwt_required()
def list_transfers():
    from ...models.addons import AssetTransfer
    rows = db.session.query(AssetTransfer).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AssetTransfer.transfer_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(t.id), "asset_id": str(t.asset_id),
                              "transfer_date": t.transfer_date.isoformat(),
                              "to_text": t.to_text, "status": t.status} for t in rows]})


@bp.post("/asset-transfers")
@jwt_required()
def create_transfer():
    denied = _deny("assets.manage")
    if denied:
        return denied
    from ...models.addons import AssetTransfer
    data = request.get_json(force=True)
    t = AssetTransfer(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        asset_id=uuid.UUID(str(data["asset_id"])),
        transfer_date=date.fromisoformat(data["transfer_date"]) if data.get("transfer_date") else date.today(),
        from_text=data.get("from_text"), to_text=data["to_text"],
        reason=data.get("reason"), status="posted",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(t)
    db.session.commit()
    return jsonify({"data": {"id": str(t.id)}}), 201


@bp.get("/asset-disposals")
@jwt_required()
def list_disposals():
    from ...models.addons import AssetDisposal
    rows = db.session.query(AssetDisposal).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AssetDisposal.disposal_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(d.id), "asset_id": str(d.asset_id),
                              "disposal_date": d.disposal_date.isoformat(),
                              "proceeds": float(d.proceeds),
                              "gain_loss": float(d.gain_loss),
                              "status": d.status} for d in rows]})


@bp.post("/asset-disposals")
@jwt_required()
def create_disposal():
    denied = _deny("assets.manage")
    if denied:
        return denied
    from ...models.addons import AssetDisposal
    from ...models.asset import Asset
    data = request.get_json(force=True)
    asset = db.session.get(Asset, uuid.UUID(str(data["asset_id"])))
    if asset is None or asset.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    proceeds = Decimal(str(data.get("proceeds", 0)))
    gain_loss = proceeds - (asset.acquisition_cost - asset.accumulated_depreciation)
    d = AssetDisposal(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=asset.entity_id,
        asset_id=asset.id,
        disposal_date=date.fromisoformat(data["disposal_date"]) if data.get("disposal_date") else date.today(),
        proceeds=float(proceeds), gain_loss=float(gain_loss),
        status="posted",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(d)
    db.session.commit()
    return jsonify({"data": {"id": str(d.id), "gain_loss": float(gain_loss)}}), 201


@bp.get("/asset-revaluations")
@jwt_required()
def list_revaluations():
    from ...models.addons import AssetRevaluation
    rows = db.session.query(AssetRevaluation).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(AssetRevaluation.reval_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(r.id), "asset_id": str(r.asset_id),
                              "reval_date": r.reval_date.isoformat(),
                              "old_cost": float(r.old_cost),
                              "new_cost": float(r.new_cost),
                              "status": r.status} for r in rows]})


@bp.post("/asset-revaluations")
@jwt_required()
def create_revaluation():
    denied = _deny("assets.manage")
    if denied:
        return denied
    from ...models.addons import AssetRevaluation
    from ...models.asset import Asset
    data = request.get_json(force=True)
    asset = db.session.get(Asset, uuid.UUID(str(data["asset_id"])))
    if asset is None or asset.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    new_cost = Decimal(str(data["new_cost"]))
    old_cost = Decimal(str(asset.acquisition_cost))
    diff = (new_cost - old_cost).quantize(Decimal("0.001"))
    r = AssetRevaluation(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=asset.entity_id,
        asset_id=asset.id,
        reval_date=date.fromisoformat(data["reval_date"]) if data.get("reval_date") else date.today(),
        old_cost=float(old_cost), new_cost=float(new_cost),
        status="posted",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(r)
    # قيد إعادة التقييم: فرق التكلفة يُرحَّل
    if abs(diff) >= Decimal("0.001"):
        try:
            from ...models.journal import Journal as _JR
            from ...models.account import Account as _AC
            journal = db.session.query(_JR).filter_by(
                tenant_id=uuid.UUID(str(g.tenant_id)), entity_id=asset.entity_id,
                code="GEN", is_deleted=False).first()
            asset_acc = db.session.query(_AC).filter_by(
                entity_id=asset.entity_id, code=asset.account_code, is_deleted=False).first() \
                if hasattr(asset, "account_code") else None
            if asset_acc is None:
                # بديل: حساب أصل ثابت 1510
                asset_acc = db.session.query(_AC).filter_by(
                    entity_id=asset.entity_id, code="1510", is_deleted=False).first()
            # حساب الفرق: تسوية أصول (5590) أو إيراد/مصروف
            gain_acc = db.session.query(_AC).filter_by(
                entity_id=asset.entity_id, code="4095", is_deleted=False).first()
            if journal and asset_acc and gain_acc:
                if diff > 0:
                    lines = [{"account_id": asset_acc.id, "debit": float(diff), "credit": 0},
                             {"account_id": gain_acc.id, "debit": 0, "credit": float(diff)}]
                else:
                    lines = [{"account_id": gain_acc.id, "debit": float(-diff), "credit": 0},
                             {"account_id": asset_acc.id, "debit": 0, "credit": float(-diff)}]
                entry = posting_service.create_entry(
                    {"tenant_id": uuid.UUID(str(g.tenant_id)), "entity_id": asset.entity_id,
                     "journal_id": journal.id, "entry_type": "revaluation",
                     "document_date": r.reval_date, "posting_date": r.reval_date,
                     "description": f"إعادة تقييم أصل {asset.code}",
                     "source_module": "assets", "source_document_id": asset.id,
                     "source_event_key": f"asset.reval.{asset.id}.{r.reval_date.isoformat()}.v1"},
                    lines, actor_id=uuid.UUID(str(get_jwt().get("sub"))))
                posting_service.post_entry(entry.id, uuid.UUID(str(get_jwt().get("sub"))))
                r.journal_entry_id = entry.id
        except Exception:
            import logging
            logging.getLogger(__name__).warning("revaluation GL failed for asset %s", asset.code, exc_info=True)
    asset.acquisition_cost = new_cost
    db.session.commit()
    return jsonify({"data": {"id": str(r.id)}}), 201


# ------------------------------------------------------------- tax groups/rates/payments

@bp.get("/tax-groups")
@jwt_required()
def list_tax_groups():
    from ...models.addons import TaxGroup
    rows = db.session.query(TaxGroup).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(TaxGroup.code).limit(PAGE).all()
    return jsonify({"data": [{"id": str(tg.id), "code": tg.code,
                              "name_ar": tg.name_ar, "is_active": tg.is_active} for tg in rows]})


@bp.post("/tax-groups")
@jwt_required()
def create_tax_group():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.addons import TaxGroup
    data = request.get_json(force=True)
    tg = TaxGroup(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        code=data["code"], name_ar=data["name_ar"], is_active=True,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(tg)
    db.session.commit()
    return jsonify({"data": {"id": str(tg.id), "code": tg.code}}), 201


@bp.get("/tax-payments")
@jwt_required()
def list_tax_payments():
    from ...models.addons import TaxPayment
    rows = db.session.query(TaxPayment).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(TaxPayment.pay_date.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(tp.id), "tax_id": str(tp.tax_id),
                              "pay_date": tp.pay_date.isoformat(),
                              "amount": float(tp.amount), "status": tp.status} for tp in rows]})


@bp.post("/tax-payments")
@jwt_required()
def create_tax_payment():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.addons import TaxPayment
    data = request.get_json(force=True)
    tp = TaxPayment(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        tax_id=uuid.UUID(str(data["tax_id"])),
        pay_date=date.fromisoformat(data["pay_date"]) if data.get("pay_date") else date.today(),
        amount=data["amount"], period_code=data.get("period_code"),
        status="draft",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(tp)
    db.session.commit()
    return jsonify({"data": {"id": str(tp.id)}}), 201


@bp.get("/withholding-taxes")
@jwt_required()
def list_withholding():
    from ...models.addons import WithholdingTax
    rows = db.session.query(WithholdingTax).filter_by(
        tenant_id=uuid.UUID(str(g.tenant_id)), is_deleted=False
    ).order_by(WithholdingTax.created_at.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(w.id), "party_id": str(w.party_id),
                              "base_amount": float(w.base_amount),
                              "rate": float(w.rate), "amount": float(w.amount),
                              "status": w.status} for w in rows]})


@bp.post("/withholding-taxes")
@jwt_required()
def create_withholding():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.addons import WithholdingTax
    data = request.get_json(force=True)
    base = Decimal(str(data["base_amount"]))
    rate = Decimal(str(data["rate"]))
    amount = (base * rate / 100).quantize(Decimal("0.001"))
    w = WithholdingTax(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        entity_id=uuid.UUID(str(data["entity_id"])),
        party_id=uuid.UUID(str(data["party_id"])),
        base_amount=float(base), rate=float(rate), amount=float(amount),
        doc_ref=data.get("doc_ref"), status="draft",
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(w)
    db.session.commit()
    return jsonify({"data": {"id": str(w.id), "amount": float(amount)}}), 201


# ------------------------------------------------------------- tax rates (indexed)

@bp.get("/tax-rates")
@jwt_required()
def list_tax_rates():
    from ...models.addons import TaxRate
    q = db.session.query(TaxRate).filter_by(is_deleted=False)
    if request.args.get("group_id"):
        q = q.filter_by(group_id=uuid.UUID(request.args["group_id"]))
    rows = q.order_by(TaxRate.valid_from.desc()).limit(PAGE).all()
    return jsonify({"data": [{"id": str(tr.id), "group_id": str(tr.group_id),
                              "tax_id": str(tr.tax_id),
                              "valid_from": tr.valid_from.isoformat(),
                              "valid_to": tr.valid_to.isoformat() if tr.valid_to else None}
                             for tr in rows]})


@bp.post("/tax-rates")
@jwt_required()
def create_tax_rate():
    denied = _deny("treasury.manage")
    if denied:
        return denied
    from ...models.addons import TaxRate
    data = request.get_json(force=True)
    tr = TaxRate(
        tenant_id=uuid.UUID(str(g.tenant_id)),
        group_id=uuid.UUID(str(data["group_id"])),
        tax_id=uuid.UUID(str(data["tax_id"])),
        valid_from=date.fromisoformat(data["valid_from"]),
        valid_to=date.fromisoformat(data["valid_to"]) if data.get("valid_to") else None,
        created_by=uuid.UUID(str(get_jwt().get("sub"))),
        updated_by=uuid.UUID(str(get_jwt().get("sub"))))
    db.session.add(tr)
    db.session.commit()
    return jsonify({"data": {"id": str(tr.id)}}), 201


# ------------------------------------------------------------- asset depreciation schedules

@bp.get("/asset-depreciation-schedules")
@jwt_required()
def list_dep_schedules():
    from ...models.addons import AssetDepreciationSchedule
    q = db.session.query(AssetDepreciationSchedule).filter_by(is_deleted=False)
    if request.args.get("asset_id"):
        q = q.filter_by(asset_id=uuid.UUID(request.args["asset_id"]))
    rows = q.order_by(AssetDepreciationSchedule.period_no).limit(PAGE).all()
    return jsonify({"data": [{"id": str(s.id), "asset_id": str(s.asset_id),
                              "period_no": s.period_no,
                              "due_on": s.due_on.isoformat(),
                              "amount": float(s.amount),
                              "status": s.status} for s in rows]})


@bp.post("/asset-depreciation-schedules")
@jwt_required()
def generate_dep_schedule():
    denied = _deny("assets.manage")
    if denied:
        return denied
    from ...models.addons import AssetDepreciationSchedule
    from ...models.asset import Asset, AssetCategory
    from dateutil.relativedelta import relativedelta
    data = request.get_json(force=True)
    asset = db.session.get(Asset, uuid.UUID(str(data["asset_id"])))
    if asset is None or asset.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    existing = db.session.query(AssetDepreciationSchedule).filter_by(
        asset_id=asset.id, is_deleted=False).count()
    if existing:
        return jsonify({"error": {"code": "DUPLICATE",
                                  "message": "schedule already exists"}}), 409
    cat = db.session.get(AssetCategory, asset.category_id)
    years = int(cat.useful_life_years) if cat else 5
    depreciable = (Decimal(str(asset.acquisition_cost))
                   - Decimal(str(asset.residual_value)))
    yearly = (depreciable / years).quantize(Decimal("0.001"))
    me = uuid.UUID(str(get_jwt().get("sub")))
    for i in range(1, years + 1):
        amt = yearly if i < years else (depreciable - yearly * (years - 1))
        db.session.add(AssetDepreciationSchedule(
            tenant_id=uuid.UUID(str(g.tenant_id)),
            asset_id=asset.id, period_no=i,
            due_on=asset.acquisition_date + relativedelta(years=i),
            amount=float(amt), status="pending",
            created_by=me, updated_by=me))
    db.session.commit()
    return jsonify({"data": {"asset_id": str(asset.id), "periods": years}}), 201


@bp.post("/asset-depreciation-schedules/<uuid:sid>/post")
@jwt_required()
def post_dep_schedule(sid):
    denied = _deny("assets.manage")
    if denied:
        return denied
    from ...models.addons import AssetDepreciationSchedule
    from ...models.asset import Asset
    from ...models.journal import Journal
    from ...services import posting_service
    s = db.session.get(AssetDepreciationSchedule, sid)
    if s is None or s.is_deleted:
        return jsonify({"error": {"code": "NOT_FOUND"}}), 404
    if s.status == "posted":
        return jsonify({"data": {"id": str(s.id), "status": s.status}})
    asset = db.session.get(Asset, s.asset_id)
    exp_acc = db.session.query(Account).filter_by(
        entity_id=asset.entity_id, code="5130", is_deleted=False).first()
    accum_acc = db.session.query(Account).filter_by(
        entity_id=asset.entity_id, code="1519", is_deleted=False).first()
    if exp_acc is None or accum_acc is None:
        return jsonify({"error": {"code": "NO_ACCOUNT",
                                  "message": "5130/1519 not configured"}}), 422
    journal = db.session.query(Journal).filter_by(
        entity_id=asset.entity_id, code="GEN", is_deleted=False).first()
    if journal is None:
        return jsonify({"error": {"code": "NO_JOURNAL"}}), 422
    me = uuid.UUID(str(get_jwt().get("sub")))
    entry = posting_service.create_entry(
        {"tenant_id": s.tenant_id, "entity_id": asset.entity_id,
         "journal_id": journal.id, "entry_type": "source",
         "document_date": s.due_on, "posting_date": s.due_on,
         "description": f"إهلاك {asset.code} قسط {s.period_no}",
         "source_module": "assets", "source_document_id": s.id,
         "source_event_key": f"assets.dep.{s.id}.v1",
         "currency_id": "JOD", "exchange_rate": 1},
        [{"account_id": exp_acc.id, "debit": float(s.amount), "credit": 0},
         {"account_id": accum_acc.id, "debit": 0, "credit": float(s.amount)}],
        actor_id=me)
    entry = posting_service.post_entry(entry.id, me)
    s.entry_id = entry.id
    s.status = "posted"
    asset.accumulated_depreciation = float(
        asset.accumulated_depreciation) + float(s.amount)
    db.session.commit()
    return jsonify({"data": {"id": str(s.id), "status": s.status,
                             "entry_id": str(entry.id)}})
