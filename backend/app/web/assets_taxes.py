"""Assets + taxes web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp_assets = Blueprint("web_assets", __name__, url_prefix="/assets")
bp_taxes = Blueprint("web_taxes", __name__, url_prefix="/taxes")


@bp_assets.get("")
def list():
    return render_template("assets/list.html", **h.ctx(
        "الأصول", [("الأصول", None), ("القائمة", None)], active="assets",
        new_url=url_for("web_assets.new"),
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
                 {"key": "net", "label": "الصافي", "num": True}, {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/assets", empty="لا أصول بعد",
        row_actions=True, detail_base="/assets"))


@bp_assets.get("/new")
def new():
    return render_template("assets/form.html", **h.ctx(
        "أصل جديد", [("الأصول", url_for("web_assets.list")), ("جديد", None)], active="assets",
        api_post="/api/v1/assets", redirect_url="/assets",
        fields=[{"name": "category_id", "label": "الفئة", "type": "select", "source": "asset_categories", "required": True},
                {"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "acquisition_date", "label": "تاريخ الاقتناء", "type": "date", "required": True},
                {"name": "acquisition_cost", "label": "كلفة الاقتناء", "type": "number", "required": True, "ltr": True}],
        cancel_url=url_for("web_assets.list")))


@bp_assets.get("/<uuid:a_id>")
def detail(a_id):
    return render_template("assets/detail.html", **h.ctx(
        "تفاصيل الأصل", [("الأصول", url_for("web_assets.list")), ("التفاصيل", None)], active="assets",
        asset_id=a_id,
        actions=[{"label": "تعديل", "url": url_for("web_assets.edit", a_id=a_id)}],
        sections=[]))


@bp_assets.get("/<uuid:a_id>/edit")
def edit(a_id):
    return render_template("assets/form.html", **h.ctx(
        "تعديل أصل", [("الأصول", url_for("web_assets.list")), ("التفاصيل", url_for("web_assets.detail", a_id=a_id)), ("تعديل", None)], active="assets",
        api_post=f"/api/v1/assets/{a_id}", redirect_url="/assets",
        method="PUT", prefill=f"/api/v1/assets/{a_id}",
        fields=[{"name": "category_id", "label": "الفئة", "type": "select", "source": "asset_categories", "required": True},
                {"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "acquisition_date", "label": "تاريخ الاقتناء", "type": "date", "required": True},
                {"name": "acquisition_cost", "label": "كلفة الاقتناء", "type": "number", "required": True, "ltr": True}],
        submit="حفظ التعديلات",
        cancel_url=url_for("web_assets.detail", a_id=a_id)))


@bp_assets.get("/depreciation")
def depreciation():
    return render_template("assets/form.html", **h.ctx(
        "الإهلاك الجماعي الشهري", [("الأصول", url_for("web_assets.list")), ("الإهلاك", None)], active="assets-d",
        api_post="/api/v1/assets/depreciate-run", redirect_url="/assets",
        fields=[{"name": "entity_id", "label": "الكيان", "type": "select", "source": "entities", "required": True},
                {"name": "posting_date", "label": "تاريخ الترحيل", "type": "date", "required": True},
                {"name": "expense_account_id", "label": "حساب المصروف", "type": "select", "source": "accounts", "required": True},
                {"name": "accum_account_id", "label": "حساب مجمع الإهلاك", "type": "select", "source": "accounts", "required": True}],
        submit="ترحيل الإهلاك الجماعي",
        cancel_url=url_for("web_assets.list")))


@bp_assets.post("/depreciation/run")
def run_depreciation():
    # الترحيل الفعلي عبر نموذج الإهلاك الجماعي (API) أعلاه.
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_assets.depreciation"))


@bp_assets.get("/<uuid:a_id>/disposal")
def disposal(a_id):
    return render_template("assets/form.html", **h.ctx(
        "استبعاد أصل", [("الأصول", url_for("web_assets.list")), ("استبعاد", None)], active="assets",
        api_post=f"/api/v1/assets/{a_id}/dispose", redirect_url="/assets",
        fields=[{"name": "disposal_date", "label": "تاريخ الاستبعاد", "type": "date", "required": True},
                {"name": "proceeds", "label": "المقبوضات", "type": "number", "ltr": True, "value": "0"},
                {"name": "asset_account_id", "label": "حساب الأصل", "type": "select", "source": "accounts", "required": True},
                {"name": "accum_account_id", "label": "حساب مجمع الإهلاك", "type": "select", "source": "accounts", "required": True},
                {"name": "cash_account_id", "label": "حساب النقدية", "type": "select", "source": "accounts"},
                {"name": "gain_account_id", "label": "حساب الربح", "type": "select", "source": "accounts"},
                {"name": "loss_account_id", "label": "حساب الخسارة", "type": "select", "source": "accounts"}],
        submit="تنفيذ الاستبعاد", cancel_url=url_for("web_assets.detail", a_id=a_id)))


@bp_assets.post("/<uuid:a_id>/disposal")
def do_disposal(a_id):
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_assets.detail", a_id=a_id))


@bp_taxes.get("")
def list():
    return render_template("taxes/list.html", **h.ctx(
        "الضرائب", [("الضرائب", None), ("القائمة", None)], active="taxes",
        new_url=url_for("web_taxes.new"),
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
                 {"key": "rate", "label": "النسبة", "num": True}],
        rows=[], api_src="/api/v1/taxes", empty="لا ضرائب معرفة",
        row_actions=True, detail_base="/taxes"))


@bp_taxes.get("/new")
def new():
    return render_template("taxes/form.html", **h.ctx(
        "ضريبة جديدة", [("الضرائب", url_for("web_taxes.list")), ("جديدة", None)], active="taxes",
        api_post="/api/v1/taxes", redirect_url="/taxes",
        fields=[{"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "rate", "label": "النسبة", "type": "number", "required": True, "ltr": True},
                {"name": "tax_type", "label": "النوع", "type": "select",
                 "options": [("sale", "مبيعات"), ("purchase", "مشتريات"), ("withholding", "اقتطاع")]}],
        cancel_url=url_for("web_taxes.list")))


@bp_taxes.get("/<uuid:t_id>")
def detail(t_id):
    return render_template("taxes/detail.html", **h.ctx(
        "تفاصيل الضريبة", [("الضرائب", url_for("web_taxes.list")), ("التفاصيل", None)], active="taxes",
        doc_kind="tax", doc_id=t_id,
        sections=[]))


@bp_taxes.get("/returns")
def returns():
    return render_template("taxes/list.html", **h.ctx(
        "الإقرارات الضريبية", [("الضرائب", url_for("web_taxes.list")), ("الإقرارات", None)], active="taxes",
        columns=[{"key": "period_code", "label": "الفترة"}, {"key": "tax_due", "label": "المستحق", "num": True}, {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/tax-returns", empty="لا إقرارات"))


@bp_taxes.get("/einvoicing")
def einvoicing():
    return render_template("taxes/list.html", **h.ctx(
        "الفوترة الإلكترونية (JoFotara — تجريبي ما لم تُضبط الشهادة)", [("الضرائب", url_for("web_taxes.list")), ("الفوترة", None)],
        active="taxes",
        columns=[{"key": "doc_number", "label": "الفاتورة"}, {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/sales/einvoicing-queue", empty="لا عناصر في الطابور"))
