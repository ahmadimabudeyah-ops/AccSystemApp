"""Projects/budgets/audit/dimensions/periods web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_projects", __name__)


@bp.get("/projects")
def projects():
    return render_template("projects/list.html", **h.ctx(
        "المشاريع", [("المشاريع", None), ("القائمة", None)], active="prj",
        new_url=url_for("web_projects.new_project"),
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
                 {"key": "costs", "label": "التكاليف", "num": True},
                 {"key": "revenues", "label": "الإيرادات", "num": True},
                 {"key": "margin", "label": "الهامش", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/projects", empty="لا مشاريع",
        row_actions=True, detail_base="/projects"))


@bp.get("/projects/new")
def new_project():
    return render_template("projects/form.html", **h.ctx(
        "مشروع جديد", [("المشاريع", url_for("web_projects.projects")), ("جديد", None)],
        active="prj", api_post="/api/v1/projects", redirect_url="/projects",
        fields=[{"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True},
                {"name": "customer_id", "label": "العميل", "type": "select", "source": "customers"},
                {"name": "budget_total", "label": "الموازنة", "type": "number", "ltr": True}],
        cancel_url=url_for("web_projects.projects")))


@bp.get("/projects/<uuid:p_id>")
def project_detail(p_id):
    return render_template("projects/detail.html", **h.ctx(
        "تفاصيل المشروع", [("المشاريع", url_for("web_projects.projects")), ("التفاصيل", None)],
        active="prj",
        doc_kind="project", doc_id=p_id,
        sections=[]))


@bp.get("/budgets")
def budgets():
    return render_template("projects/list.html", **h.ctx(
        "الموازنات", [("المشاريع", None), ("الموازنات", None)], active="bud",
        new_url=url_for("web_projects.new_budget"),
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/budgets", empty="لا موازنات"))


@bp.get("/budgets/new")
def new_budget():
    return render_template("projects/form.html", **h.ctx(
        "موازنة جديدة", [("المشاريع", url_for("web_projects.budgets")), ("جديدة", None)],
        active="bud", api_post="/api/v1/budgets", redirect_url="/budgets",
        fields=[{"name": "fiscal_year_id", "label": "السنة المالية", "type": "select", "source": "fiscal_years", "required": True},
                {"name": "code", "label": "الرمز", "required": True, "ltr": True},
                {"name": "name_ar", "label": "الاسم", "required": True}],
        cancel_url=url_for("web_projects.budgets")))


@bp.get("/audit-logs")
def audit_logs():
    return render_template("settings/list.html", **h.ctx(
        "سجل التدقيق", [("الإعدادات", url_for("web_settings.index")), ("التدقيق", None)],
        active="settings",
        columns=[{"key": "action", "label": "الإجراء"}, {"key": "entity_type", "label": "الكيان"},
                 {"key": "created_at", "label": "الوقت"}],
        rows=[], api_src="/api/v1/audit-logs", empty="لا أحداث"))


@bp.get("/dimensions")
def dimensions():
    return render_template("settings/list.html", **h.ctx(
        "الأبعاد التحليلية", [("الإعدادات", url_for("web_settings.index")), ("الأبعاد", None)],
        active="settings",
        columns=[{"key": "code", "label": "الرمز"}, {"key": "name_ar", "label": "الاسم"},
                 {"key": "dim_type", "label": "النوع"}],
        rows=[], api_src="/api/v1/dimensions", empty="لا أبعاد"))


@bp.get("/periods")
def periods():
    return render_template("settings/list.html", **h.ctx(
        "الفترات المالية", [("الإعدادات", url_for("web_settings.index")), ("الفترات", None)],
        active="settings",
        columns=[{"key": "code", "label": "الفترة"}, {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/fiscal-periods", empty="لا فترات"))
