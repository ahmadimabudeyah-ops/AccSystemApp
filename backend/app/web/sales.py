"""Sales web pages (Quote-to-Cash)."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_sales", __name__, url_prefix="/sales")

INV_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "customer_name", "label": "العميل"},
            {"key": "grand_total", "label": "الإجمالي", "num": True},
            {"key": "remaining_amount", "label": "المتبقي", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]
PAY_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "customer_name", "label": "العميل"},
            {"key": "amount", "label": "المبلغ", "num": True},
            {"key": "unallocated_amount", "label": "غير مخصص", "num": True},
            {"key": "status", "label": "الحالة", "badge": True}]
STUB_COLS = [{"key": "doc_number", "label": "الرقم"},
             {"key": "status", "label": "الحالة", "badge": True}]
LIVE_COLS = [{"key": "doc_number", "label": "الرقم"},
             {"key": "grand_total", "label": "الإجمالي", "num": True},
             {"key": "status", "label": "الحالة", "badge": True}]


def _doc_list(title, crumb, active, endpoint, new_endpoint=None):
    return render_template("sales/list.html", **h.ctx(
        title, [("المبيعات", None), (crumb, None)], active=active,
        new_url=url_for(new_endpoint) if new_endpoint else None,
        columns=STUB_COLS, rows=[], empty="لا مستندات بعد",
        row_actions=True, detail_base=endpoint.rsplit(".", 1)[0].replace("web_sales.", "/sales/") if False else None))


@bp.get("/quotations")
def quotations():
    return render_template("sales/list.html", **h.ctx(
        "عروض الأسعار", [("المبيعات", None), ("العروض", None)], active="sales-q",
        new_url=url_for("web_sales.new_quotation"), columns=LIVE_COLS, rows=[],
        api_src="/api/v1/sales/quotations", empty="لا عروض بعد"))


@bp.get("/quotations/new")
def new_quotation():
    return render_template("sales/form.html", **h.ctx(
        "عرض سعر جديد", [("المبيعات", None), ("العروض", url_for("web_sales.quotations")), ("جديد", None)],
        active="sales-q", api_post="/api/v1/sales/quotations", redirect_url="/sales/quotations",
        single_line=True,
        fields=[{"name": "customer_id", "label": "العميل", "type": "select", "source": "customers", "required": True},
                {"name": "valid_days", "label": "صالح لمدة (يوم)", "type": "number", "value": 15},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "unit_price", "label": "سعر الوحدة", "type": "number", "required": True, "ltr": True}],
        cancel_url=url_for("web_sales.quotations")))


@bp.get("/quotations/<uuid:q_id>")
def quotation_detail(q_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل العرض", [("المبيعات", None), ("العروض", url_for("web_sales.quotations")), ("التفاصيل", None)],
        active="sales-q", doc_kind="quotation", doc_id=q_id,
        actions=[{"label": "تحويل لأمر بيع", "api": True, "api_base": "/api/v1/sales/quotations",
                  "api_id": q_id, "api_action": "convert", "style": "gold"}],
        sections=[]))


@bp.post("/quotations/<uuid:q_id>/convert")
def convert_quotation(q_id):
    # التنفيذ الفعلي عبر زر التفاصيل (API). لا نجاح شكلي هنا.
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_sales.quotation_detail", q_id=q_id))


@bp.get("/orders")
def orders():
    return render_template("sales/list.html", **h.ctx(
        "أوامر البيع", [("المبيعات", None), ("الأوامر", None)], active="sales-o",
        new_url=url_for("web_sales.new_order"), columns=LIVE_COLS, rows=[],
        api_src="/api/v1/sales/orders", empty="لا أوامر بعد"))


@bp.get("/orders/new")
def new_order():
    return render_template("sales/form.html", **h.ctx(
        "أمر بيع جديد (من عرض)", [("المبيعات", None), ("الأوامر", url_for("web_sales.orders")), ("جديد", None)],
        active="sales-o", api_post="/api/v1/sales/orders", redirect_url="/sales/orders",
        fields=[{"name": "quotation_id", "label": "عرض السعر", "type": "select", "source": "quotations", "required": True}],
        cancel_url=url_for("web_sales.orders")))


@bp.get("/orders/<uuid:o_id>")
def order_detail(o_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل الأمر", [("المبيعات", None), ("الأوامر", url_for("web_sales.orders")), ("التفاصيل", None)],
        active="sales-o", doc_kind="sales_order", doc_id=o_id,
        actions=[{"label": "فوترة الأمر", "api": True, "api_base": "/api/v1/sales/orders",
                  "api_id": o_id, "api_action": "invoice", "style": "primary"}],
        sections=[]))


@bp.post("/orders/<uuid:o_id>/confirm")
def confirm_order(o_id):
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_sales.order_detail", o_id=o_id))


@bp.get("/deliveries/new")
def new_delivery():
    return render_template("sales/form.html", **h.ctx(
        "تسليم جديد (من أمر)", [("المبيعات", None), ("التسليمات", url_for("web_sales.deliveries")), ("جديد", None)],
        active="sales-d", api_post="/api/v1/sales/deliveries", redirect_url="/sales/deliveries",
        fields=[{"name": "order_id", "label": "أمر البيع", "type": "select", "source": "sales_orders", "required": True},
                {"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses", "required": True}],
        cancel_url=url_for("web_sales.deliveries")))


@bp.get("/deliveries")
def deliveries():
    return render_template("sales/list.html", **h.ctx(
        "التسليمات", [("المبيعات", None), ("التسليمات", None)],         active="sales-d",
        new_url=url_for("web_sales.new_delivery"),
        columns=LIVE_COLS, rows=[], api_src="/api/v1/sales/deliveries", empty="لا تسليمات بعد"))


@bp.get("/deliveries/<uuid:d_id>")
def delivery_detail(d_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل التسليم", [("المبيعات", None), ("التسليمات", url_for("web_sales.deliveries")), ("التفاصيل", None)],
        active="sales-d", doc_kind="delivery", doc_id=d_id,
        actions=[{"label": "تأكيد التسليم", "api": True, "api_base": "/api/v1/sales/deliveries",
                  "api_id": d_id, "api_action": "confirm", "style": "primary"}],
        sections=[]))


@bp.get("/invoices")
def invoices():
    return render_template("sales/list.html", **h.ctx(
        "فواتير العملاء", [("المبيعات", None), ("الفواتير", None)], active="sales-i",
        new_url=url_for("web_sales.new_invoice"), columns=INV_COLS, rows=[],
        api_src="/api/v1/sales/invoices", empty="لا فواتير بعد",
        row_actions=True, detail_base="/sales/invoices", export=True))


@bp.get("/invoices/new")
def new_invoice():
    return render_template("sales/invoice_form.html", **h.ctx(
        "فاتورة جديدة", [("المبيعات", None), ("الفواتير", url_for("web_sales.invoices")), ("جديدة", None)],
        active="sales-i"))


@bp.post("/invoices")
def create_invoice():
    """Legacy route: invoice creation is handled by invoice_form.html against
    the API, so this only exists so old links do not 404."""
    return redirect(url_for("web_sales.invoices"))


@bp.get("/invoices/<uuid:i_id>")
def invoice_detail(i_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل الفاتورة", [("المبيعات", None), ("الفواتير", url_for("web_sales.invoices")), ("التفاصيل", None)],
        active="sales-i", doc_kind="invoice", doc_id=i_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/sales/invoices",
                  "api_id": i_id, "api_action": "post", "style": "primary"},
                 {"label": "إرسال إلكتروني", "api": True,
                  "api_base": "/api/v1/sales/einvoicing/process",
                  "api_action": "post"},
                 {"label": "طباعة", "url": url_for("web_sales.print_invoice", i_id=i_id)}],
        sections=[]))


@bp.post("/invoices/<uuid:i_id>/post")
def post_invoice(i_id):
    """Legacy route: posting runs through the API from the detail page button."""
    return redirect(url_for("web_sales.invoice_detail", i_id=i_id))


@bp.post("/invoices/<uuid:i_id>/send")
def send_invoice(i_id):
    """Legacy route kept for compatibility.

    The e-invoicing queue is driven by the API (POST /api/v1/sales/einvoicing/process)
    triggered from the invoice detail page, so this route simply returns the
    client to the detail page where the real action lives.
    """
    return redirect(url_for("web_sales.invoice_detail", i_id=i_id))


@bp.get("/invoices/<uuid:i_id>/print")
def print_invoice(i_id):
    return render_template("sales/detail.html", **h.ctx(
        "طباعة فاتورة", [("المبيعات", None), ("الفواتير", url_for("web_sales.invoices")), ("طباعة", None)],
        active="sales-i", doc_kind="invoice", doc_id=i_id,
        actions=[{"label": "رجوع للفاتورة", "url": url_for("web_sales.invoice_detail", i_id=i_id)}],
        sections=[]))


@bp.get("/payments")
def payments():
    return render_template("sales/list.html", **h.ctx(
        "الدفعات", [("المبيعات", None), ("الدفعات", None)], active="sales-p",
        new_url=url_for("web_sales.new_payment"), columns=PAY_COLS, rows=[],
        api_src="/api/v1/sales/payments", empty="لا دفعات بعد",
        row_actions=True, detail_base="/sales/payments"))


@bp.get("/payments/<uuid:pay_id>")
def payment_detail(pay_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل الدفعة", [("المبيعات", None), ("الدفعات", url_for("web_sales.payments")), ("التفاصيل", None)],
        active="sales-p", doc_kind="payment", doc_id=pay_id,
        sections=[]))


@bp.get("/payments/new")
def new_payment():
    return render_template("sales/form.html", **h.ctx(
        "دفعة جديدة", [("المبيعات", None), ("الدفعات", url_for("web_sales.payments")), ("جديدة", None)],
        active="sales-p", api_post="/api/v1/sales/payments", redirect_url="/sales/payments",
        fields=[{"name": "customer_id", "label": "العميل", "type": "select", "source": "customers", "required": True},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "pay_method", "label": "الطريقة", "type": "select",
                 "options": [("cash", "نقد"), ("bank_transfer", "تحويل"), ("check", "شيك")]},
                {"name": "reference", "label": "المرجع", "ltr": True}],
        cancel_url=url_for("web_sales.payments")))


@bp.get("/returns")
def returns():
    return render_template("sales/list.html", **h.ctx(
        "المرتجعات", [("المبيعات", None), ("المرتجعات", None)], active="sales-r",
        new_url=url_for("web_sales.new_return"),
        columns=[{"key": "doc_number", "label": "الرقم"},
                 {"key": "total_amount", "label": "المبلغ", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/sales/returns", empty="لا مرتجعات",
        detail_base="/sales/returns"))


@bp.get("/returns/<uuid:ret_id>")
def return_detail(ret_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل المرتجع", [("المبيعات", None), ("المرتجعات", url_for("web_sales.returns")), ("التفاصيل", None)],
        active="sales-r", doc_kind="return", doc_id=ret_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/sales/returns",
                  "api_id": ret_id, "api_action": "post", "style": "primary"}],
        sections=[]))


@bp.get("/returns/new")
def new_return():
    return render_template("sales/form.html", **h.ctx(
        "مرتجع جديد", [("المبيعات", None), ("المرتجعات", url_for("web_sales.returns")), ("جديد", None)],
        active="sales-r", api_post="/api/v1/sales/returns", redirect_url="/sales/returns",
        single_line=True,
        fields=[{"name": "customer_id", "label": "العميل", "type": "select", "source": "customers", "required": True},
                {"name": "invoice_id", "label": "الفاتورة الأصلية", "type": "select", "source": "sales_invoices"},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "returned_qty", "label": "الكمية المرتجعة", "type": "number", "required": True, "ltr": True},
                {"name": "unit_price", "label": "سعر الوحدة", "type": "number", "required": True, "ltr": True},
                {"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses"},
                {"name": "reason", "label": "السبب", "type": "textarea", "required": True}],
        cancel_url=url_for("web_sales.returns")))


@bp.get("/credit-notes")
def credit_notes():
    return render_template("sales/list.html", **h.ctx(
        "الإشعارات الدائنة", [("المبيعات", None), ("الإشعارات", None)], active="sales-r",
        columns=[{"key": "doc_number", "label": "الرقم"},
                 {"key": "grand_total", "label": "المبلغ", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/sales/credit-notes", empty="لا إشعارات",
        detail_base="/sales/credit-notes"))


@bp.get("/credit-notes/<uuid:note_id>")
def credit_note_detail(note_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل الإشعار الدائن", [("المبيعات", None), ("الإشعارات", url_for("web_sales.credit_notes")), ("التفاصيل", None)],
        active="sales-r", doc_kind="credit_note", doc_id=note_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/sales/credit-notes",
                  "api_id": note_id, "api_action": "post", "style": "primary"}],
        sections=[]))


@bp.get("/debit-notes")
def debit_notes():
    return render_template("sales/list.html", **h.ctx(
        "الإشعارات المدينة", [("المبيعات", None), ("الإشعارات", None)], active="sales-r",
        new_url=url_for("web_sales.new_debit_note"),
        columns=[{"key": "doc_number", "label": "الرقم"},
                 {"key": "grand_total", "label": "المبلغ", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/sales/debit-notes", empty="لا إشعارات مدينة",
        row_actions=True, detail_base="/sales/debit-notes"))


@bp.get("/debit-notes/new")
def new_debit_note():
    return render_template("sales/form.html", **h.ctx(
        "إشعار مدين جديد", [("المبيعات", None), ("الإشعارات", url_for("web_sales.debit_notes")), ("جديد", None)],
        active="sales-r", api_post="/api/v1/sales/debit-notes", redirect_url="/sales/debit-notes",
        single_line=True,
        fields=[{"name": "customer_id", "label": "العميل", "type": "select", "source": "customers", "required": True},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products"},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "unit_price", "label": "سعر الوحدة", "type": "number", "required": True, "ltr": True},
                {"name": "reason", "label": "السبب", "type": "textarea", "required": True}],
        cancel_url=url_for("web_sales.debit_notes")))


@bp.get("/debit-notes/<uuid:note_id>")
def debit_note_detail(note_id):
    return render_template("sales/detail.html", **h.ctx(
        "تفاصيل الإشعار المدين", [("المبيعات", None), ("الإشعارات", url_for("web_sales.debit_notes")), ("التفاصيل", None)],
        active="sales-r", doc_kind="debit_note", doc_id=note_id,
        actions=[{"label": "ترحيل", "api": True, "api_base": "/api/v1/sales/debit-notes",
                  "api_id": note_id, "api_action": "post", "style": "primary"}],
        sections=[]))
