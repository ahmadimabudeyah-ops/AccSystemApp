"""Inventory + products already have web_products; this covers stock ops."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_inventory", __name__, url_prefix="/inventory")

MOVE_COLS = [{"key": "doc_number", "label": "الرقم"}, {"key": "product_name", "label": "الصنف"},
           {"key": "qty", "label": "الكمية", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]
QUANT_COLS = [{"key": "product_code", "label": "الصنف"}, {"key": "location_code", "label": "الموقع"},
              {"key": "qty", "label": "الكمية", "num": True}, {"key": "available", "label": "المتاح", "num": True}]


def _list(title, crumb, active, new_ep=None, columns=None, api_src=None):
    return render_template("inventory/list.html", **h.ctx(
        title, [("المخزون", None), (crumb, None)], active=active,
        new_url=url_for(new_ep) if new_ep else None,
        columns=columns or MOVE_COLS, rows=[], api_src=api_src, empty="لا حركات بعد"))


@bp.get("/moves")
def moves():
    return _list("حركات المخزون", "الحركات", "inv-m", "web_inventory.new_move",
                 MOVE_COLS, "/api/v1/inventory/moves")


@bp.get("/moves/new")
def new_move():
    return render_template("inventory/form.html", **h.ctx(
        "حركة جديدة", [("المخزون", None), ("الحركات", url_for("web_inventory.moves")), ("جديدة", None)],
        active="inv-m", api_post="/api/v1/inventory/moves", redirect_url="/inventory/moves",
        fields=[{"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses",
                 "warehouse_for": "source_location_id,dest_location_id", "required": True},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "uom_id", "label": "الوحدة", "type": "select", "source": "uoms", "required": True},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "move_type", "label": "النوع", "type": "select",
                 "options": [("receipt", "استلام"), ("delivery", "تسليم"), ("internal", "داخلي"), ("adjustment", "تسوية")]},
                {"name": "source_location_id", "label": "الموقع المصدر", "type": "select"},
                {"name": "dest_location_id", "label": "الموقع الهدف", "type": "select"}],
        cancel_url=url_for("web_inventory.moves")))


@bp.get("/quants")
def quants():
    return render_template("inventory/list.html", **h.ctx(
        "أرصدة المخزون", [("المخزون", None), ("الأرصدة", None)], active="inv-q",
        columns=QUANT_COLS,
        rows=[], api_src="/api/v1/inventory/quants", empty="لا أرصدة"))


@bp.get("/adjustments")
def adjustments():
    return _list("تعديلات الجرد", "التعديلات", "inv-q", "web_inventory.new_adjustment",
                 MOVE_COLS, "/api/v1/inventory/moves?move_type=adjustment")


@bp.get("/adjustments/new")
def new_adjustment():
    return render_template("inventory/form.html", **h.ctx(
        "تعديل جديد", [("المخزون", None), ("التعديلات", url_for("web_inventory.adjustments")), ("جديد", None)],
        active="inv-q", api_post="/api/v1/inventory/moves", redirect_url="/inventory/moves",
        fields=[{"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses",
                 "warehouse_for": "dest_location_id", "required": True},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "uom_id", "label": "الوحدة", "type": "select", "source": "uoms", "required": True},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "move_type", "label": "النوع", "type": "hidden", "value": "adjustment"},
                {"name": "dest_location_id", "label": "الموقع", "type": "select"},
                {"name": "reason", "label": "السبب", "type": "textarea", "required": True}],
        cancel_url=url_for("web_inventory.adjustments")))


@bp.post("/adjustments")
def create_adjustment():
    # الإنشاء الفعلي عبر api_post أعلاه (يحمل JWT). هذا المسار القديم لا يحفظ.
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_inventory.adjustments"))


@bp.get("/counts")
def counts():
    return render_template("inventory/list.html", **h.ctx(
        "الجرد الفعلي", [("المخزون", None), ("الجرد", None)], active="inv-c",
        new_url=url_for("web_inventory.new_count"),
        columns=[{"key": "doc_number", "label": "الرقم"},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/inventory/counts", empty="لا جرد بعد",
        row_actions=True, detail_base="/inventory/counts"))


@bp.get("/counts/new")
def new_count():
    return render_template("inventory/form.html", **h.ctx(
        "جرد جديد", [("المخزون", None), ("الجرد", url_for("web_inventory.counts")), ("جديد", None)],
        active="inv-c", api_post="/api/v1/inventory/counts", redirect_url="/inventory/counts",
        fields=[{"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses", "required": True},
                {"name": "notes", "label": "ملاحظات", "type": "textarea"}],
        cancel_url=url_for("web_inventory.counts")))


@bp.get("/counts/<uuid:c_id>")
def count_detail(c_id):
    return render_template("inventory/count_detail.html", **h.ctx(
        "تفاصيل الجرد", [("المخزون", None), ("الجرد", url_for("web_inventory.counts")), ("التفاصيل", None)],
        active="inv-c", count_id=c_id))


@bp.post("/counts")
def create_count():
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_inventory.counts"))


@bp.get("/transfers")
def transfers():
    return _list("التحويلات", "التحويلات", "inv-t", "web_inventory.new_transfer",
                 MOVE_COLS, "/api/v1/inventory/moves?move_type=internal")


@bp.get("/transfers/new")
def new_transfer():
    return render_template("inventory/form.html", **h.ctx(
        "تحويل جديد", [("المخزون", None), ("التحويلات", url_for("web_inventory.transfers")), ("جديد", None)],
        active="inv-t", api_post="/api/v1/inventory/moves", redirect_url="/inventory/moves",
        fields=[{"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses",
                 "warehouse_for": "source_location_id,dest_location_id", "required": True},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "uom_id", "label": "الوحدة", "type": "select", "source": "uoms", "required": True},
                {"name": "qty", "label": "الكمية", "type": "number", "required": True, "ltr": True},
                {"name": "move_type", "label": "النوع", "type": "hidden", "value": "internal"},
                {"name": "source_location_id", "label": "الموقع المصدر", "type": "select", "required": True},
                {"name": "dest_location_id", "label": "الموقع الهدف", "type": "select", "required": True}],
        cancel_url=url_for("web_inventory.transfers")))


@bp.post("/transfers")
def create_transfer():
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_inventory.transfers"))


@bp.get("/scrap")
def scrap():
    return render_template("inventory/list.html", **h.ctx(
        "التالف", [("المخزون", None), ("التالف", None)], active="inv-t",
        new_url=url_for("web_inventory.new_scrap"),
        columns=MOVE_COLS, rows=[], api_src="/api/v1/inventory/moves", empty="لا حركات بعد"))


@bp.get("/scrap/new")
def new_scrap():
    return render_template("inventory/form.html", **h.ctx(
        "تالف جديد", [("المخزون", None), ("التالف", url_for("web_inventory.scrap")), ("جديد", None)],
        active="inv-t", api_post="/api/v1/inventory/moves", redirect_url="/inventory/moves",
        fields=[{"name": "warehouse_id", "label": "المستودع", "type": "select", "source": "warehouses",
                 "warehouse_for": "source_location_id", "required": True},
                {"name": "product_id", "label": "الصنف", "type": "select", "source": "products", "required": True},
                {"name": "uom_id", "label": "الوحدة", "type": "select", "source": "uoms", "required": True},
                {"name": "qty", "label": "الكمية التالفة", "type": "number", "required": True, "ltr": True},
                {"name": "move_type", "label": "النوع", "type": "hidden", "value": "adjustment"},
                {"name": "source_location_id", "label": "الموقع المصدر", "type": "select", "required": True},
                {"name": "reference", "label": "السبب/المرجع", "type": "textarea", "required": True}],
        cancel_url=url_for("web_inventory.scrap")))
