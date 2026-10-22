"""Reports web pages: index + generic viewer."""
from flask import Blueprint, render_template, abort
from . import _helpers as h

bp = Blueprint("web_reports", __name__, url_prefix="/reports")

REPORTS = [
    ("trial-balance", "ميزان المراجعة"),
    ("ledger", "الأستاذ العام"),
    ("account-statement", "كشف حساب تفصيلي"),
    ("balance-sheet", "الميزانية العمومية"),
    ("income-statement", "قائمة الدخل"),
    ("cash-flow", "التدفقات النقدية"),
    ("aging-receivables", "أعمار الذمم المدينة"),
    ("aging-payables", "أعمار الذمم الدائنة"),
    ("inventory", "تقارير المخزون"),
    ("assets", "تقارير الأصول"),
    ("tax", "تقارير الضرائب"),
    ("budget", "تقارير الموازنات"),
]


@bp.get("")
def index():
    return render_template("reports/index.html", **h.ctx(
        "التقارير", [("التقارير", None)], active="reports", reports=REPORTS))


@bp.get("/<name>")
def view(name):
    titles = dict(REPORTS)
    if name not in titles:
        abort(404)
    return render_template("reports/view.html", **h.ctx(
        titles[name], [("التقارير", "/reports"), (titles[name], None)], active="reports",
        report_name=name, table=None))


@bp.get("/schedules/list")
def schedules():
    return render_template("reports/schedules.html", **h.ctx(
        "جدولة التقارير", [("التقارير", "/reports"), ("الجدولة", None)], active="reports",
        columns=[{"key": "report_code", "label": "التقرير"}, {"key": "cron", "label": "الجدولة"},
                 {"key": "is_active", "label": "نشط"}],
        rows=[], api_src="/api/v1/report-schedules", empty="لا جدولة"))
