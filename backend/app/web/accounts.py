"""Accounts web pages."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_accounts", __name__, url_prefix="/accounts")

FIELDS = [
    {"name": "code", "label": "الرمز", "required": True, "ltr": True},
    {"name": "name_ar", "label": "الاسم العربي", "required": True},
    {"name": "name_en", "label": "الاسم الإنجليزي", "ltr": True},
    {"name": "account_type", "label": "النوع", "type": "select", "required": True,
     "options": [("asset", "أصول"), ("liability", "التزامات"), ("equity", "حقوق ملكية"),
                 ("income", "إيرادات"), ("expense", "مصروفات")]},
    {"name": "normal_balance", "label": "الطبيعة", "type": "select", "required": True,
     "options": [("debit", "مدين"), ("credit", "دائن")]},
]


@bp.get("")
def list():
    cols = [{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
            {"key": "account_type", "label": "النوع"}, {"key": "normal_balance", "label": "الطبيعة"}]
    return render_template("accounts/list.html", **h.ctx(
        "دليل الحسابات", [("المحاسبة", None), ("دليل الحسابات", None)], active="accounts",
        search_action=url_for("web_accounts.list"), new_url=url_for("web_accounts.new"),
        columns=cols, rows=[], api="accounts", empty="لا حسابات بعد — أنشئ أول حساب", row_actions=True,
        detail_base="/accounts", export=True))


@bp.get("/tree")
def tree():
    return render_template("accounts/tree.html", **h.ctx(
        "شجرة الحسابات", [("المحاسبة", None), ("دليل الحسابات", url_for("web_accounts.list")),
                           ("الشجرة", None)], active="accounts-tree"))


@bp.get("/new")
def new():
    return render_template("accounts/form.html", **h.ctx(
        "حساب جديد", [("المحاسبة", None), ("دليل الحسابات", url_for("web_accounts.list")),
                       ("جديد", None)], active="accounts",
         api_post="/api/v1/accounts", redirect_url="/accounts", fields=FIELDS, submit="حفظ",
        cancel_url=url_for("web_accounts.list")))


@bp.get("/<uuid:acc_id>")
def detail(acc_id):
    return render_template("accounts/detail.html", **h.ctx(
        "تفاصيل الحساب", [("المحاسبة", None), ("دليل الحسابات", url_for("web_accounts.list")),
                           ("التفاصيل", None)], active="accounts",
        doc_kind="account", doc_id=acc_id,
        actions=[{"label": "تعديل", "url": url_for("web_accounts.edit", acc_id=acc_id)}],
        sections=[]))


@bp.get("/<uuid:acc_id>/edit")
def edit(acc_id):
    return render_template("accounts/form.html", **h.ctx(
        "تعديل حساب", [("المحاسبة", None), ("دليل الحسابات", url_for("web_accounts.list")),
                        ("تعديل", None)], active="accounts",
        api_post=f"/api/v1/accounts/{acc_id}", method="PUT", redirect_url="/accounts",
        prefill=f"/api/v1/accounts/{acc_id}", fields=FIELDS,
        submit="حفظ التعديلات", cancel_url=url_for("web_accounts.detail", acc_id=acc_id)))
