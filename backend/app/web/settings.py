"""Settings web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_settings", __name__, url_prefix="/settings")


@bp.get("")
def index():
    links = [("العامة", url_for("web_settings.general")), ("الشركة", url_for("web_settings.company")),
             ("الفروع", url_for("web_settings.branches")), ("المستخدمون", url_for("web_settings.users")),
             ("الأدوار", url_for("web_settings.roles")), ("العملات", url_for("web_settings.currencies")),
             ("الفترات المالية", url_for("web_settings.fiscal_years")),
             ("السياسات", url_for("web_settings.policies")),
             ("استيراد وتصدير", url_for("web_settings.import_export")),
             ("الملف الشخصي", url_for("web_settings.profile"))]
    return render_template("settings/index.html", **h.ctx(
        "الإعدادات", [("الإعدادات", None)], active="settings", links=links))


def _simple(title, crumb, active, rows_cols=None):
    cols, rows = rows_cols or ([{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"}], [])
    return render_template("settings/list.html", **h.ctx(
        title, [("الإعدادات", url_for("web_settings.index")), (crumb, None)], active=active,
        columns=cols, rows=rows, empty="لا بيانات"))


@bp.get("/general")
def general():
    return render_template("settings/form.html", **h.ctx(
        "الإعدادات العامة", [("الإعدادات", url_for("web_settings.index")), ("عامة", None)],
        active="settings", api_post="/api/v1/settings/general", redirect_url="/settings/general",
        method="PUT", prefill="/api/v1/settings/general",
        fields=[{"name": "currency", "label": "العملة الوظيفية", "ltr": True, "value": "JOD"},
                {"name": "timezone", "label": "المنطقة الزمنية", "ltr": True, "value": "Asia/Amman"}],
        cancel_url=url_for("web_settings.index")))


@bp.post("/general")
def save_general():
    # الحفظ الفعلي عبر api_post (PUT) أعلاه — هذا المسار القديم لا يحفظ.
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_settings.general"))


@bp.get("/company")
def company():
    return render_template("settings/form.html", **h.ctx(
        "بيانات الشركة", [("الإعدادات", url_for("web_settings.index")), ("الشركة", None)],
        active="settings", api_post="/api/v1/settings/company", redirect_url="/settings/company",
        method="PUT", prefill="/api/v1/settings/company",
        fields=[{"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "tax_id", "label": "الرقم الضريبي", "ltr": True}],
        cancel_url=url_for("web_settings.index")))


@bp.post("/company")
def save_company():
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_settings.company"))


@bp.get("/branches")
def branches():
    return render_template("settings/list.html", **h.ctx(
        "الفروع", [("الإعدادات", url_for("web_settings.index")), ("الفروع", None)],
        active="set-b",
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"}],
        rows=[], api_src="branches", empty="لا فروع"))


@bp.get("/users")
def users():
    return render_template("settings/list.html", **h.ctx(
        "المستخدمون", [("الإعدادات", url_for("web_settings.index")), ("المستخدمون", None)],
        active="set-u", new_url=url_for("web_settings.new_user"),
        columns=[{"key": "username", "label": "المستخدم"}, {"key": "email", "label": "البريد"},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api="users", empty="لا مستخدمين",
        row_actions=True, detail_base="/settings/users"))


@bp.get("/users/new")
def new_user():
    return render_template("settings/form.html", **h.ctx(
        "مستخدم جديد", [("الإعدادات", url_for("web_settings.index")),
                         ("المستخدمون", url_for("web_settings.users")), ("جديد", None)],
        active="set-u", api_post="/api/v1/users", redirect_url="/settings/users",
        fields=[{"name": "username", "label": "اسم المستخدم", "required": True, "ltr": True},
                {"name": "email", "label": "البريد", "type": "email", "required": True, "ltr": True},
                {"name": "password", "label": "كلمة المرور", "type": "password", "required": True, "ltr": True},
                {"name": "role_id", "label": "الدور", "type": "select", "source": "roles"}],
        cancel_url=url_for("web_settings.users")))


@bp.post("/users")
def create_user():
    # المسار القديم بدون JWT — الإنشاء الفعلي عبر api_post أعلاه.
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_settings.users"))


@bp.get("/users/<u_id>")
def user_detail(u_id):
    return render_template("settings/detail.html", **h.ctx(
        "تفاصيل المستخدم", [("الإعدادات", url_for("web_settings.index")),
                             ("المستخدمون", url_for("web_settings.users")), ("التفاصيل", None)],
        active="set-u",
        doc_kind="user", doc_id=u_id,
        actions=[{"label": "تعديل", "url": url_for("web_settings.edit_user", u_id=u_id)}],
        sections=[]))


@bp.get("/users/<u_id>/edit")
def edit_user(u_id):
    return render_template("settings/form.html", **h.ctx(
        "تعديل مستخدم", [("الإعدادات", url_for("web_settings.index")),
                         ("المستخدمون", url_for("web_settings.users")), ("تعديل", None)],
        active="set-u", api_post=f"/api/v1/users/{u_id}", redirect_url="/settings/users",
        method="PUT", prefill=f"/api/v1/users/{u_id}",
        fields=[{"name": "is_active", "label": "الحالة", "type": "select",
                 "options": [("true", "نشط"), ("false", "موقوف")]},
                {"name": "password", "label": "كلمة مرور جديدة (اتركها فارغة للإبقاء)",
                 "type": "password", "ltr": True},
                {"name": "role_id", "label": "الدور", "type": "select", "source": "roles"}],
        submit="حفظ التعديلات",
        cancel_url=url_for("web_settings.user_detail", u_id=u_id)))


@bp.get("/roles")
def roles():
    return render_template("settings/list.html", **h.ctx(
        "الأدوار", [("الإعدادات", url_for("web_settings.index")), ("الأدوار", None)],
        active="set-r", new_url=url_for("web_settings.new_role"),
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"}],
        rows=[], api_src="/api/v1/roles", empty="لا أدوار",
        row_actions=True, detail_base="/settings/roles"))


@bp.get("/roles/new")
def new_role():
    return render_template("settings/form.html", **h.ctx(
        "دور جديد", [("الإعدادات", url_for("web_settings.index")),
                      ("الأدوار", url_for("web_settings.roles")), ("جديد", None)],
        active="set-r", api_post="/api/v1/roles", redirect_url="/settings/roles",
        fields=[{"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True}],
        cancel_url=url_for("web_settings.roles")))


@bp.post("/roles")
def create_role():
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_settings.roles"))


@bp.get("/roles/<r_id>")
def role_detail(r_id):
    return render_template("settings/detail.html", **h.ctx(
        "تفاصيل الدور", [("الإعدادات", url_for("web_settings.index")),
                          ("الأدوار", url_for("web_settings.roles")), ("التفاصيل", None)],
        active="set-r",
        doc_kind="role", doc_id=r_id,
        actions=[{"label": "تعديل", "url": url_for("web_settings.edit_role", r_id=r_id)}],
        sections=[]))


@bp.get("/roles/<r_id>/edit")
def edit_role(r_id):
    return render_template("settings/form.html", **h.ctx(
        "تعديل دور", [("الإعدادات", url_for("web_settings.index")),
                      ("الأدوار", url_for("web_settings.roles")), ("تعديل", None)],
        active="set-r", api_post=f"/api/v1/roles/{r_id}", redirect_url="/settings/roles",
        method="PUT", prefill=f"/api/v1/roles/{r_id}",
        fields=[{"name": "name_ar", "label": "الاسم", "required": True}],
        submit="حفظ التعديلات",
        cancel_url=url_for("web_settings.role_detail", r_id=r_id)))


@bp.get("/currencies")
def currencies():
    return render_template("settings/list.html", **h.ctx(
        "العملات", [("الإعدادات", url_for("web_settings.index")), ("العملات", None)],
        active="settings",
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"}],
        rows=[], api_src="/api/v1/currencies", empty="لا عملات"))


@bp.get("/fiscal-years")
def fiscal_years():
    return render_template("settings/list.html", **h.ctx(
        "الفترات المالية", [("الإعدادات", url_for("web_settings.index")), ("الفترات", None)],
        active="settings",
        columns=[{"key": "code", "label": "السنة"}, {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/tenants/fiscal-years", empty="لا فترات"))


@bp.get("/policies")
def policies():
    return render_template("settings/list.html", **h.ctx(
        "السياسات المحاسبية", [("الإعدادات", url_for("web_settings.index")), ("السياسات", None)],
        active="settings",
        columns=[{"key": "code", "label": "الرمز"}, {"key": "framework", "label": "الإطار"},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/policies", empty="لا سياسات"))


@bp.get("/import-export")
def import_export():
    return render_template("settings/import_export.html", **h.ctx(
        "استيراد وتصدير", [("الإعدادات", url_for("web_settings.index")), ("البيانات", None)],
        active="settings"))


@bp.get("/profile")
def profile():
    return render_template("settings/form.html", **h.ctx(
        "الملف الشخصي", [("الإعدادات", url_for("web_settings.index")), ("الملف", None)],
        active="settings", api_post="/api/v1/users/me", redirect_url="/settings/profile",
        method="PUT", prefill="/api/v1/users/me", no_append=True,
        fields=[{"name": "full_name", "label": "الاسم الكامل"},
                {"name": "email", "label": "البريد", "type": "email", "ltr": True}],
        cancel_url=url_for("web_settings.index")))


@bp.post("/profile")
def save_profile():
    # Legacy route: the real action runs against the API (api_post / api button).
    return redirect(url_for("web_settings.profile"))
