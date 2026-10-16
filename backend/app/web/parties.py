"""Parties web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_parties", __name__, url_prefix="/parties")

FIELDS = [
    {"name": "code", "label": "الرمز", "required": True, "ltr": True},
    {"name": "name_ar", "label": "الاسم", "required": True},
    {"name": "credit_limit", "label": "الحد الائتماني", "type": "number", "ltr": True},
]

COLS = [{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
        {"key": "credit_limit", "label": "الحد الائتماني", "num": True},
        {"key": "status", "label": "الحالة", "badge": True}]


def _list(title, crumb, active, kind=""):
    src = "/api/v1/parties" + (f"?type={kind}" if kind else "")
    return render_template("parties/list.html", **h.ctx(
        title, [("الأطراف", url_for("web_parties.list")), (crumb, None)], active=active,
        new_url=url_for("web_parties.new"), columns=COLS, rows=[], api_src=src,
        empty="لا أطراف بعد", row_actions=True, detail_base="/parties"))


@bp.get("")
def list():
    return _list("الأطراف", "الكل", "parties")


@bp.get("/customers")
def customers():
    return _list("العملاء", "العملاء", "parties-c", kind="customer")


@bp.get("/suppliers")
def suppliers():
    return _list("الموردون", "الموردون", "parties-s", kind="supplier")


@bp.get("/new")
def new():
    return render_template("parties/form.html", **h.ctx(
        "طرف جديد", [("الأطراف", url_for("web_parties.list")), ("جديد", None)], active="parties",
        api_post="/api/v1/parties", redirect_url="/parties",
        fields=FIELDS, cancel_url=url_for("web_parties.list")))


@bp.get("/<uuid:p_id>")
def detail(p_id):
    return render_template("parties/detail.html", **h.ctx(
        "تفاصيل الطرف", [("الأطراف", url_for("web_parties.list")), ("التفاصيل", None)], active="parties",
        doc_kind="party", doc_id=p_id,
        actions=[{"label": "تعديل", "url": url_for("web_parties.edit", p_id=p_id)},
                 {"label": "كشف حساب", "url": url_for("web_parties.statement", p_id=p_id)}],
        sections=[]))


@bp.get("/<uuid:p_id>/edit")
def edit(p_id):
    return render_template("parties/form.html", **h.ctx(
        "تعديل طرف", [("الأطراف", url_for("web_parties.list")), ("تعديل", None)], active="parties",
        api_post=f"/api/v1/parties/{p_id}", method="PUT", redirect_url="/parties",
        prefill=f"/api/v1/parties/{p_id}", fields=FIELDS,
        cancel_url=url_for("web_parties.detail", p_id=p_id)))


@bp.get("/<uuid:p_id>/statement")
def statement(p_id):
    return render_template("parties/statement.html", **h.ctx(
        "كشف حساب", [("الأطراف", url_for("web_parties.list")),
                      ("التفاصيل", url_for("web_parties.detail", p_id=p_id)), ("الكشف", None)],
        active="parties",
        table={"title": "الحركات", "columns": [
            {"key": "date", "label": "التاريخ"}, {"key": "doc", "label": "المستند"},
            {"key": "debit", "label": "مدين", "num": True}, {"key": "credit", "label": "دائن", "num": True}],
               "rows": []}))
