"""Journal entries web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_entries", __name__, url_prefix="/journal-entries")


@bp.get("")
def list():
    cols = [{"key": "official_number", "label": "الرقم"}, {"key": "posting_date", "label": "التاريخ"},
            {"key": "description", "label": "البيان"}, {"key": "total_debit", "label": "مدين", "num": True},
            {"key": "total_credit", "label": "دائن", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]
    return render_template("journal_entries/list.html", **h.ctx(
        "القيود اليومية", [("المحاسبة", None), ("القيود", None)], active="entries",
        new_url=url_for("web_entries.new"), columns=cols, rows=[], api="entries",
        empty="لا قيود بعد — أنشئ أول قيد", row_actions=True, detail_base="/journal-entries", export=True))


@bp.get("/new")
def new():
    return render_template("journal_entries/form.html", **h.ctx(
        "قيد جديد", [("المحاسبة", None), ("القيود", url_for("web_entries.list")), ("جديد", None)],
        active="entries"))


@bp.get("/<uuid:e_id>")
def detail(e_id):
    return render_template("journal_entries/detail.html", **h.ctx(
        "تفاصيل القيد", [("المحاسبة", None), ("القيود", url_for("web_entries.list")), ("التفاصيل", None)],
        active="entries", eid=e_id,
        actions=[],
        sections=[]))


@bp.get("/<uuid:e_id>/reverse")
def reverse(e_id):
    return render_template("journal_entries/reverse.html", **h.ctx(
        "عكس قيد", [("المحاسبة", None), ("القيود", url_for("web_entries.list")), ("عكس", None)],
        active="entries", api_post=f"/api/v1/journal-entries/{e_id}/reverse",
        redirect_url=f"/journal-entries/{e_id}",
        fields=[{"name": "reason", "label": "سبب العكس", "type": "textarea", "required": True},
                {"name": "reversal_date", "label": "تاريخ العكس", "type": "date", "required": True}],
        submit="تنفيذ العكس", cancel_url=url_for("web_entries.detail", e_id=e_id)))


@bp.get("/<uuid:e_id>/approve")
def approve(e_id):
    return render_template("journal_entries/approve.html", **h.ctx(
        "اعتماد قيد", [("المحاسبة", None), ("القيود", url_for("web_entries.list")), ("اعتماد", None)],
        active="entries", api_post=f"/api/v1/journal-entries/{e_id}/approve",
        redirect_url=f"/journal-entries/{e_id}",
        fields=[{"name": "approver_id", "label": "معرف المعتمد", "required": True, "ltr": True},
                {"name": "reason", "label": "ملاحظة", "type": "textarea"}],
        submit="اعتماد", cancel_url=url_for("web_entries.detail", e_id=e_id)))
