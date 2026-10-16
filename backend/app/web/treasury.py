"""Treasury web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_treasury", __name__, url_prefix="/treasury")

COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "party", "label": "الطرف"},
        {"key": "amount", "label": "المبلغ", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]


def _list(title, crumb, active, new_ep=None, columns=None, api_src=None, detail_base=None):
    return render_template("treasury/list.html", **h.ctx(
        title, [("الخزينة", None), (crumb, None)], active=active,
        new_url=url_for(new_ep) if new_ep else None,
        columns=columns or [{"key": "doc_number", "label": "الرقم"},
                             {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src=api_src, row_actions=bool(detail_base), detail_base=detail_base,
        empty="لا بيانات بعد"))


TXN_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "txn_type", "label": "النوع"},
            {"key": "amount", "label": "المبلغ", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]
BOX_COLS = [{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
            {"key": "currency_id", "label": "العملة"}]
BANK_COLS = [{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"}]
ACCT_COLS = [{"key": "code", "label": "الرمز"}, {"key": "iban", "label": "الآيبان"},
             {"key": "currency_id", "label": "العملة"}]
CHECK_COLS = [{"key": "check_no", "label": "الشيك"}, {"key": "payee", "label": "المستفيد"},
              {"key": "amount", "label": "المبلغ", "num": True},
              {"key": "due_on", "label": "الاستحقاق"},
              {"key": "status", "label": "الحالة", "badge": True}]
TR_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "amount", "label": "المبلغ", "num": True},
           {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/cash-boxes")
def cash_boxes():
    return _list("الصناديق", "الصناديق", "tre-cb", "web_treasury.new_cash_box",
                 BOX_COLS, "/api/v1/treasury/cash-boxes", "/treasury/cash-boxes")


@bp.get("/cash-boxes/new")
def new_cash_box():
    return render_template("treasury/form.html", **h.ctx(
        "صندوق جديد", [("الخزينة", None), ("الصناديق", url_for("web_treasury.cash_boxes")), ("جديد", None)],
        active="tre-cb", api_post="/api/v1/treasury/cash-boxes", redirect_url="/treasury/cash-boxes",
        fields=[{"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "opening_balance", "label": "الرصيد الافتتاحي", "type": "number", "ltr": True}],
        cancel_url=url_for("web_treasury.cash_boxes")))


@bp.get("/cash-boxes/<uuid:b_id>")
def cash_box_detail(b_id):
    return render_template("treasury/detail.html", **h.ctx(
        "تفاصيل الصندوق", [("الخزينة", None), ("الصناديق", url_for("web_treasury.cash_boxes")), ("التفاصيل", None)],
        active="tre-cb",
        doc_kind="cash_box", doc_id=b_id,
        sections=[]))


@bp.get("/cash-transactions")
def cash_transactions():
    return _list("حركات النقد", "الحركات", "tre-ct", "web_treasury.new_cash_transaction",
                 TXN_COLS, "/api/v1/treasury/cash-transactions")


@bp.get("/cash-transactions/new")
def new_cash_transaction():
    return render_template("treasury/form.html", **h.ctx(
        "حركة نقد جديدة", [("الخزينة", None), ("الحركات", url_for("web_treasury.cash_transactions")), ("جديدة", None)],
        active="tre-ct", api_post="/api/v1/treasury/cash-transactions", redirect_url="/treasury/cash-transactions",
        fields=[{"name": "box_id", "label": "الصندوق", "type": "select", "source": "boxes", "required": True},
                {"name": "txn_type", "label": "النوع", "type": "select",
                 "options": [("in", "قبض"), ("out", "صرف")]},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "cash_account_id", "label": "حساب النقدية", "type": "select", "source": "accounts", "required": True},
                {"name": "offset_account_id", "label": "الحساب المقابل", "type": "select", "source": "accounts", "required": True},
                {"name": "description", "label": "البيان", "type": "textarea"}],
        cancel_url=url_for("web_treasury.cash_transactions")))


@bp.get("/banks")
def banks():
    return _list("البنوك", "البنوك", "tre-b", "web_treasury.new_bank",
                 BANK_COLS, "/api/v1/treasury/banks")


@bp.get("/banks/new")
def new_bank():
    return render_template("treasury/form.html", **h.ctx(
        "بنك جديد", [("الخزينة", None), ("البنوك", url_for("web_treasury.banks")), ("جديد", None)],
        active="tre-b", api_post="/api/v1/treasury/banks", redirect_url="/treasury/banks",
        fields=[{"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True}],
        cancel_url=url_for("web_treasury.banks")))


@bp.get("/bank-accounts")
def bank_accounts():
    return _list("الحسابات البنكية", "الحسابات", "tre-b", "web_treasury.new_bank_account",
                 ACCT_COLS, "/api/v1/treasury/bank-accounts")


@bp.get("/bank-accounts/new")
def new_bank_account():
    return render_template("treasury/form.html", **h.ctx(
        "حساب بنكي جديد", [("الخزينة", None), ("الحسابات", url_for("web_treasury.bank_accounts")), ("جديد", None)],
        active="tre-b", api_post="/api/v1/treasury/bank-accounts", redirect_url="/treasury/bank-accounts",
        fields=[{"name": "bank_id", "label": "البنك", "type": "select", "source": "banks", "required": True},
                {"name": "code", "label": "رمز الحساب", "required": True, "ltr": True},
                {"name": "iban", "label": "الآيبان", "ltr": True},
                {"name": "opening_balance", "label": "الرصيد الافتتاحي", "type": "number", "ltr": True}],
        cancel_url=url_for("web_treasury.bank_accounts")))


@bp.get("/bank-statements")
def bank_statements():
    return _list("كشوف البنوك", "الكشوف", "tre-b", "web_treasury.new_bank_statement",
                 [{"key": "id", "label": "المعرف"}, {"key": "status", "label": "الحالة", "badge": True}],
                 "/api/v1/treasury/bank-statements")


@bp.get("/bank-statements/new")
def new_bank_statement():
    return render_template("treasury/form.html", **h.ctx(
        "كشف جديد", [("الخزينة", None), ("الكشوف", url_for("web_treasury.bank_statements")), ("جديد", None)],
        active="tre-b", api_post="/api/v1/treasury/bank-statements/import", redirect_url="/treasury/bank-statements",
        fields=[{"name": "bank_account_id", "label": "الحساب البنكي", "type": "select", "source": "bank_accounts", "required": True},
                {"name": "lines", "label": "البنود (JSON)", "type": "textarea"}],
        cancel_url=url_for("web_treasury.bank_statements")))


@bp.get("/bank-reconciliation")
def bank_reconciliation():
    return render_template("treasury/list.html", **h.ctx(
        "المطابقة البنكية", [("الخزينة", None), ("المطابقة", None)], active="tre-b",
        columns=[{"key": "doc_number", "label": "المستند"}, {"key": "amount", "label": "المبلغ", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/treasury/bank-statements", empty="اختر كشفًا للمطابقة من قائمة الكشوف"))


@bp.get("/checks")
def checks():
    return _list("الشيكات", "الشيكات", "tre-ch", "web_treasury.new_check",
                 CHECK_COLS, "/api/v1/treasury/checks", "/treasury/checks")


@bp.get("/checks/new")
def new_check():
    return render_template("treasury/form.html", **h.ctx(
        "شيك جديد", [("الخزينة", None), ("الشيكات", url_for("web_treasury.checks")), ("جديد", None)],
        active="tre-ch", api_post="/api/v1/treasury/checks", redirect_url="/treasury/checks",
        fields=[{"name": "bank_account_id", "label": "الحساب البنكي", "type": "select", "source": "bank_accounts", "required": True},
                {"name": "check_no", "label": "رقم الشيك", "required": True, "ltr": True},
                {"name": "payee", "label": "المستفيد", "required": True},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "due_on", "label": "الاستحقاق", "type": "date", "required": True}],
        cancel_url=url_for("web_treasury.checks")))


@bp.get("/checks/<uuid:c_id>")
def check_detail(c_id):
    return render_template("treasury/detail.html", **h.ctx(
        "تفاصيل الشيك", [("الخزينة", None), ("الشيكات", url_for("web_treasury.checks")), ("التفاصيل", None)],
        active="tre-ch",
        doc_kind="check", doc_id=c_id,
        sections=[]))


@bp.get("/transfers")
def transfers():
    return _list("التحويلات", "التحويلات", "tre-t", "web_treasury.new_transfer",
                 TR_COLS, "/api/v1/treasury/transfers")


@bp.get("/transfers/new")
def new_transfer():
    return render_template("treasury/form.html", **h.ctx(
        "تحويل جديد", [("الخزينة", None), ("التحويلات", url_for("web_treasury.transfers")), ("جديد", None)],
        active="tre-t", api_post="/api/v1/treasury/transfers", redirect_url="/treasury/transfers",
        fields=[{"name": "from_account_id", "label": "من حساب (أستاذ)", "type": "select", "source": "accounts", "required": True},
                {"name": "to_account_id", "label": "إلى حساب (أستاذ)", "type": "select", "source": "accounts", "required": True},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "notes", "label": "ملاحظات"}],
        cancel_url=url_for("web_treasury.transfers")))


# ------------------------------------------------------------- check books

CB_COLS = [{"key": "code", "label": "الرمز"}, {"key": "start_no", "label": "من رقم", "ltr": True},
           {"key": "end_no", "label": "إلى رقم", "ltr": True},
           {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/check-books")
def check_books():
    return _list("دفاتر الشيكات", "دفاتر الشيكات", "tre-cb", "web_treasury.new_check_book",
                 CB_COLS, "/api/v1/treasury/check-books")


@bp.get("/check-books/new")
def new_check_book():
    return render_template("treasury/form.html", **h.ctx(
        "دفتر شيكات جديد", [("الخزينة", None), ("دفاتر الشيكات", url_for("web_treasury.check_books")), ("جديد", None)],
        active="tre-cb", api_post="/api/v1/treasury/check-books", redirect_url="/treasury/check-books",
        fields=[{"name": "bank_account_id", "label": "الحساب البنكي", "type": "select", "source": "accounts", "required": True},
                {"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "start_no", "label": "من رقم", "required": True, "ltr": True},
                {"name": "end_no", "label": "إلى رقم", "required": True, "ltr": True}],
        cancel_url=url_for("web_treasury.check_books")))


# ------------------------------------------------------------- bank reconciliations

REC_COLS = [{"key": "reconciled_on", "label": "تاريخ التسوية"},
            {"key": "matched_count", "label": "عدد المطابقات", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/bank-reconciliations")
def bank_reconciliations():
    return _list("التسويات المصرفية", "التسويات", "tre-bs", None,
                 REC_COLS, "/api/v1/treasury/bank-reconciliations")
