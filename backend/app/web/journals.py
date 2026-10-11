"""Journals web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_journals", __name__, url_prefix="/journals")

FIELDS = [
    {"name": "code", "label": "الرمز", "required": True, "ltr": True},
    {"name": "name", "label": "الاسم", "required": True},
    {"name": "type", "label": "النوع", "type": "select", "required": True,
     "options": [("sale", "مبيعات"), ("purchase", "مشتريات"), ("cash", "نقدية"),
                 ("bank", "بنكية"), ("general", "عامة")]},
]


@bp.get("")
def list():
    cols = [{"key": "code", "label": "الرمز"}, {"key": "name", "label": "الاسم"}, {"key": "type", "label": "النوع"}]
    return render_template("journals/list.html", **h.ctx(
        "الدفاتر", [("المحاسبة", None), ("الدفاتر", None)], active="journals",
        new_url=url_for("web_journals.new"), columns=cols, rows=[],
        api_src="/api/v1/journals", empty="لا دفاتر بعد",
        row_actions=True, detail_base="/journals"))


@bp.get("/new")
def new():
    return render_template("journals/form.html", **h.ctx(
        "دفتر جديد", [("المحاسبة", None), ("الدفاتر", url_for("web_journals.list")), ("جديد", None)],
        active="journals", api_post="/api/v1/journals", redirect_url="/journals",
        fields=FIELDS,
        cancel_url=url_for("web_journals.list")))


@bp.get("/<uuid:j_id>")
def detail(j_id):
    return render_template("journals/detail.html", **h.ctx(
        "تفاصيل الدفتر", [("المحاسبة", None), ("الدفاتر", url_for("web_journals.list")), ("التفاصيل", None)],
        active="journals",
        doc_kind="journal", doc_id=j_id,
        actions=[{"label": "تعديل", "url": url_for("web_journals.edit", j_id=j_id)}],
        sections=[]))


@bp.get("/<uuid:j_id>/edit")
def edit(j_id):
    return render_template("journals/form.html", **h.ctx(
        "تعديل دفتر", [("المحاسبة", None), ("الدفاتر", url_for("web_journals.list")), ("تعديل", None)],
        active="journals", action=url_for("web_journals.detail", j_id=j_id), fields=FIELDS,
        cancel_url=url_for("web_journals.detail", j_id=j_id)))
