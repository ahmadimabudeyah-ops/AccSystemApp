"""Assets + taxes + currencies API."""
from __future__ import annotations
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt
from ...extensions import db
from ...models.asset import Asset, AssetCategory
from ...models.treasury import Currency, Tax
from ...services import posting_service
from ...services.errors import AccountingError

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
                             "acquisition_cost": float(a.acquisition_cost),
                             "accumulated_depreciation": float(a.accumulated_depreciation),
                             "net": float(a.acquisition_cost) - float(a.accumulated_depreciation),
                             "status": a.status}})


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
    try:
        from ...models.journal import Journal
        journal = db.session.query(Journal).filter_by(
            tenant_id=a.tenant_id, entity_id=a.entity_id, code="GEN", is_deleted=False).first()
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
                              "tax_due": float(r.tax_due), "status": r.status} for r in rows]})


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
                             "tax_due": float(ret.tax_due), "status": ret.status}}), 201


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
