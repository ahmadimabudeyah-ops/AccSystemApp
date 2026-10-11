"""Purchases web pages (Request-to-Pay)."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_purchases", __name__, url_prefix="/purchases")

BILL_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "supplier_name", "label": "المورد"},
            {"key": "grand_total", "label": "الإجمالي", "num": True},
            {"key": "remaining_amount", "label": "المتبقي", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]
VPAY_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "amount", "label": "المبلغ", "num": True},
            {"key": "unallocated_amount", "label": "غير مخصص", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]
STUB_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "status", "label": "الحالة", "badge": True}]


def _list(title, crumb, active, new_ep=None, columns=None, api_src=None, detail_base=None):
    return render_template("purchases/list.html", **h.ctx(
        title, [("المشتريات", None), (crumb, None)], active=active,
        new_url=url_for(new_ep) if new_ep else None,
        columns=columns or STUB_COLS, rows=[], api_src=api_src,
        row_actions=bool(detail_base), detail_base=detail_base,
        empty="لا مستندات بعد"))


DOC_LIVE = [{"key": "doc_number", "label": "الرقم"},
            {"key": "grand_total", "label": "الإجمالي", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/requests")
def requests():
    return _list("طلبات الشراء", "الطلبات", "pur-r", "web_purchases.new_request",
                 DOC_LIVE, "/api/v1/purchases/requests", "/purchases/requests")


@bp.get("/requests/new")
def new_request():
    return render_template("purchases/form.html", **h.ctx(
        "طلب شراء جديد", [("المشتريات", None), ("الطلبات", url_for("web_purchases.requests")), ("جديد", None)],
        active="pur-r", api_post="/api/v1/purchases/requests", redirect_url="/purchases/requests",
        single_line=True,
        fields=[{"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "reason", "label": "السبب", "type": "textarea", "required": True}],
        cancel_url=url_for("web_purchases.requests")))


@bp.get("/requests/<uuid:r_id>")
def request_detail(r_id):
    return render_template("purchases/detail.html", **h.ctx(
        "تفاصيل الطلب", [("المشتريات", None), ("الطلبات", url_for("web_purchases.requests")), ("التفاصيل", None)],
        active="pur-r", doc_kind="purchase_request", doc_id=r_id,
        actions=[{"label": "اعتماد", "api": True, "api_base": "/api/v1/purchases/requests",
                  "api_id": r_id, "api_action": "approve", "style": "gold"}],
        sections=[]))


@bp.post("/requests/<uuid:r_id>/approve")
def approve_request(r_id):
    flash("استخدم زر الاعتماد في صفحة التفاصيل — لم يُنفذ اعتماد", "error")
    return redirect(url_for("web_purchases.request_detail", r_id=r_id))


@bp.get("/orders")
def orders():
    return _list("أوامر الشراء", "الأوامر", "pur-o", "web_purchases.new_order",
                 DOC_LIVE, "/api/v1/purchases/orders", "/purchases/orders")


@bp.get("/orders/new")
def new_order():
    return render_template("purchases/form.html", **h.ctx(
        "أمر شراء جديد", [("المشتريات", None), ("الأوامر", url_for("web_purchases.orders")), ("جديد", None)],
        active="pur-o", api_post="/api/v1/purchases/orders", redirect_url="/purchases/orders",
        single_line=True,
        fields=[{"name": "supplier_id", "label": "المورد", "type": "select", "source": "suppliers", "required": True},
                {"name": "request_id", "label": "طلب الشراء", "type": "select", "source": "purchase_requests"},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "ordered_qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "unit_price", "label": "سعر الوحدة", "type": "number", "required": True, "ltr": True}],
        cancel_url=url_for("web_purchases.orders")))


@bp.get("/orders/<uuid:o_id>")
def order_detail(o_id):
    return render_template("purchases/detail.html", **h.ctx(
        "تفاصيل الأمر", [("المشتريات", None), ("الأوامر", url_for("web_purchases.orders")), ("التفاصيل", None)],
        active="pur-o", doc_kind="purchase_order", doc_id=o_id,
        actions=[{"label": "إنشاء فاتورة", "url": url_for("web_purchases.new_bill") + f"?order_id={o_id}", "style": "primary"},
                 {"label": "مطابقة ثلاثية", "url": url_for("web_purchases.bills") + f"?order_id={o_id}", "style": "gold"}],
        sections=[]))


@bp.get("/receipts")
def receipts():
    return _list("الاستلامات", "الاستلامات", "pur-g", "web_purchases.new_receipt",
                 DOC_LIVE, "/api/v1/purchases/receipts", "/purchases/receipts")


@bp.get("/receipts/new")
def new_receipt():
    return render_template("purchases/form.html", **h.ctx(
        "استلام جديد (من أمر)", [("المشتريات", None), ("الاستلامات", url_for("web_purchases.receipts")), ("جديد", None)],
        active="pur-g", api_post="/api/v1/purchases/receipts", redirect_url="/purchases/receipts",
        fields=[{"name": "order_id", "label": "أمر الشراء", "type": "select", "source": "purchase_orders", "required": True},
                {"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses", "required": True}],
        cancel_url=url_for("web_purchases.receipts")))


@bp.get("/receipts/<uuid:g_id>")
def receipt_detail(g_id):
    return render_template("purchases/detail.html", **h.ctx(
        "تفاصيل الاستلام", [("المشتريات", None), ("الاستلامات", url_for("web_purchases.receipts")), ("التفاصيل", None)],
        active="pur-g", doc_kind="receipt", doc_id=g_id,
        actions=[{"label": "تأكيد الاستلام", "api": True, "api_base": "/api/v1/purchases/receipts",
                  "api_id": g_id, "api_action": "confirm", "style": "primary"}],
        sections=[]))


@bp.get("/bills")
def bills():
    return _list("فواتير الموردين", "الفواتير", "pur-b", "web_purchases.new_bill",
                 BILL_COLS, "/api/v1/purchases/bills", "/purchases/bills")


@bp.get("/bills/new")
def new_bill():
    return render_template("purchases/bill_form.html", **h.ctx(
        "فاتورة مورد جديدة", [("المشتريات", None), ("الفواتير", url_for("web_purchases.bills")), ("جديدة", None)],
        active="pur-b"))


@bp.post("/bills")
def create_bill():
    flash("استخدم نموذج فاتورة المورد — الحفظ عبر API فقط", "error")
    return redirect(url_for("web_purchases.bills"))


@bp.get("/bills/<uuid:b_id>")
def bill_detail(b_id):
    return render_template("purchases/detail.html", **h.ctx(
        "تفاصيل الفاتورة", [("المشتريات", None), ("الفواتير", url_for("web_purchases.bills")), ("التفاصيل", None)],
        active="pur-b", doc_kind="bill", doc_id=b_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/purchases/bills",
                  "api_id": b_id, "api_action": "post", "style": "primary"},
                 {"label": "تأكيد المطابقة الثلاثية", "api": True, "api_base": "/api/v1/purchases/bills",
                  "api_id": b_id, "api_action": "match/confirm", "style": "gold"}],
        sections=[]))


@bp.post("/bills/<uuid:b_id>/match")
def match_bill(b_id):
    # التنفيذ الفعلي عبر زر التأكيد في صفحة التفاصيل (API).
    flash("استخدم زر تأكيد المطابقة في صفحة التفاصيل — لم تُنفذ مطابقة", "error")
    return redirect(url_for("web_purchases.bill_detail", b_id=b_id))


@bp.post("/bills/<uuid:b_id>/post")
def post_bill(b_id):
    flash("استخدم زر الترحيل في صفحة التفاصيل — لم يُرحّل شيء", "error")
    return redirect(url_for("web_purchases.bill_detail", b_id=b_id))


@bp.get("/payments")
def payments():
    return _list("دفعات الموردين", "الدفعات", "pur-p", "web_purchases.new_payment",
                 VPAY_COLS, "/api/v1/purchases/payments")


@bp.get("/payments/new")
def new_payment():
    return render_template("purchases/form.html", **h.ctx(
        "دفعة جديدة", [("المشتريات", None), ("الدفعات", url_for("web_purchases.payments")), ("جديدة", None)],
        active="pur-p", api_post="/api/v1/purchases/payments", redirect_url="/purchases/payments",
        fields=[{"name": "supplier_id", "label": "المورد", "type": "select", "source": "suppliers", "required": True},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "pay_method", "label": "الطريقة", "type": "select",
                 "options": [("bank_transfer", "تحويل"), ("cash", "نقد"), ("check", "شيك")]}],
        cancel_url=url_for("web_purchases.payments")))


@bp.get("/returns")
def returns():
    return _list("مرتجعات المشتريات", "المرتجعات", "pur-p",
                 "web_purchases.new_vendor_return",
                 [{"key": "doc_number", "label": "الرقم"},
                  {"key": "total_amount", "label": "المبلغ", "num": True},
                  {"key": "status", "label": "الحالة", "badge": True}],
                 "/api/v1/purchases/returns",
                 detail_base="/purchases/returns")


@bp.get("/returns/<uuid:ret_id>")
def vendor_return_detail(ret_id):
    return render_template("purchases/detail.html", **h.ctx(
        "تفاصيل المرتجع", [("المشتريات", None), ("المرتجعات", url_for("web_purchases.returns")), ("التفاصيل", None)],
        active="pur-p", doc_kind="vendor_return", doc_id=ret_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/purchases/returns",
                  "api_id": ret_id, "api_action": "post", "style": "primary"}],
        sections=[]))


@bp.get("/returns/new")
def new_vendor_return():
    return render_template("purchases/form.html", **h.ctx(
        "مرتجع مشتريات جديد", [("المشتريات", None), ("المرتجعات", url_for("web_purchases.returns")), ("جديد", None)],
        active="pur-p", api_post="/api/v1/purchases/returns", redirect_url="/purchases/returns",
        single_line=True,
        fields=[{"name": "supplier_id", "label": "المورد", "type": "select", "source": "suppliers", "required": True},
                {"name": "bill_id", "label": "فاتورة المورد", "type": "select", "source": "purchase_bills"},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "returned_qty", "label": "الكمية المرتجعة", "type": "number", "required": True, "ltr": True},
                {"name": "unit_price", "label": "سعر الوحدة", "type": "number", "required": True, "ltr": True},
                {"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses"},
                {"name": "reason", "label": "السبب", "type": "textarea", "required": True}],
        cancel_url=url_for("web_purchases.returns")))
