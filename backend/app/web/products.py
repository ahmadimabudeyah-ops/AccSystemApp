"""Products web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_products", __name__, url_prefix="/products")

FIELDS = [
    {"name": "code", "label": "الرمز", "required": True, "ltr": True},
    {"name": "name_ar", "label": "الاسم", "required": True},
    {"name": "category_id", "label": "الفئة", "type": "select", "source": "product_categories"},
    {"name": "base_uom_id", "label": "الوحدة", "type": "select", "source": "uoms"},
    {"name": "standard_cost", "label": "التكلفة المعيارية", "type": "number", "ltr": True},
    {"name": "sale_price", "label": "سعر البيع", "type": "number", "ltr": True},
]


@bp.get("")
def list():
    cols = [{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
            {"key": "sale_price", "label": "السعر", "num": True}]
    return render_template("products/list.html", **h.ctx(
        "الأصناف", [("المخزون", None), ("الأصناف", None)], active="products",
        new_url=url_for("web_products.new"), columns=cols, rows=[], api_src="/api/v1/products",
        empty="لا أصناف بعد", row_actions=True, detail_base="/products"))


@bp.get("/new")
def new():
    return render_template("products/form.html", **h.ctx(
        "صنف جديد", [("المخزون", None), ("الأصناف", url_for("web_products.list")), ("جديد", None)],
        active="products", api_post="/api/v1/products", redirect_url="/products",
        fields=FIELDS,
        cancel_url=url_for("web_products.list")))


@bp.get("/<uuid:p_id>")
def detail(p_id):
    return render_template("products/detail.html", **h.ctx(
        "تفاصيل الصنف", [("المخزون", None), ("الأصناف", url_for("web_products.list")), ("التفاصيل", None)],
        active="products",
        doc_kind="product", doc_id=p_id,
        actions=[{"label": "تعديل", "url": url_for("web_products.edit", p_id=p_id)}],
        sections=[]))


@bp.get("/<uuid:p_id>/edit")
def edit(p_id):
    return render_template("products/form.html", **h.ctx(
        "تعديل صنف", [("المخزون", None), ("الأصناف", url_for("web_products.list")), ("تعديل", None)],
        active="products", api_post=f"/api/v1/products/{p_id}", method="PUT",
        redirect_url="/products", prefill=f"/api/v1/products/{p_id}", fields=FIELDS,
        cancel_url=url_for("web_products.detail", p_id=p_id)))
