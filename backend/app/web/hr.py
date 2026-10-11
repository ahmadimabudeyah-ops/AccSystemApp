"""HR web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_hr", __name__, url_prefix="/hr")

EMP_COLS = [{"key": "employee_no", "label": "الرقم"}, {"key": "full_name_ar", "label": "الاسم"},
            {"key": "gross", "label": "الإجمالي", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]
RUN_COLS = [{"key": "run_code", "label": "المسيرة"}, {"key": "pay_month", "label": "الشهر"},
            {"key": "total_net", "label": "الصافي", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/employees")
def employees():
    return render_template("hr/list.html", **h.ctx(
        "الموظفون", [("الموارد البشرية", None), ("الموظفون", None)], active="hr-e",
        new_url=url_for("web_hr.new_employee"), columns=EMP_COLS, rows=[],
        api_src="/api/v1/hr/employees", empty="لا موظفين",
        row_actions=True, detail_base="/hr/employees"))


@bp.get("/employees/new")
def new_employee():
    return render_template("hr/form.html", **h.ctx(
        "موظف جديد", [("الموارد البشرية", None), ("الموظفون", url_for("web_hr.employees")), ("جديد", None)],
        active="hr-e", api_post="/api/v1/hr/employees", redirect_url="/hr/employees",
        fields=[{"name": "employee_no", "label": "الرقم", "required": True, "ltr": True},
                {"name": "full_name_ar", "label": "الاسم", "required": True},
                {"name": "basic_salary", "label": "الأساسي", "type": "number", "required": True, "ltr": True},
                {"name": "hire_date", "label": "التعيين", "type": "date"}],
        cancel_url=url_for("web_hr.employees")))


@bp.get("/employees/<uuid:e_id>")
def employee_detail(e_id):
    return render_template("hr/detail.html", **h.ctx(
        "ملف الموظف", [("الموارد البشرية", None), ("الموظفون", url_for("web_hr.employees")), ("التفاصيل", None)],
        active="hr-e",
        doc_kind="employee", doc_id=e_id,
        sections=[]))


@bp.get("/payroll-runs")
def runs():
    return render_template("hr/list.html", **h.ctx(
        "مسيرات الرواتب", [("الموارد البشرية", None), ("المسيرات", None)], active="hr-r",
        new_url=url_for("web_hr.new_run"), columns=RUN_COLS, rows=[],
        api_src="/api/v1/hr/payroll-runs", empty="لا مسيرات",
        row_actions=True, detail_base="/hr/payroll-runs"))


@bp.get("/payroll-runs/new")
def new_run():
    return render_template("hr/form.html", **h.ctx(
        "مسيرة جديدة", [("الموارد البشرية", None), ("المسيرات", url_for("web_hr.runs")), ("جديدة", None)],
        active="hr-r", api_post="/api/v1/hr/payroll-runs", redirect_url="/hr/payroll-runs",
        fields=[{"name": "fiscal_period_id", "label": "الفترة المالية", "type": "select", "source": "periods", "required": True},
                {"name": "pay_month", "label": "شهر الاستحقاق", "type": "date", "required": True}],
        cancel_url=url_for("web_hr.runs")))


@bp.get("/payroll-runs/<uuid:r_id>")
def run_detail(r_id):
    return render_template("hr/detail.html", **h.ctx(
        "تفاصيل المسيرة", [("الموارد البشرية", None), ("المسيرات", url_for("web_hr.runs")), ("التفاصيل", None)],
        active="hr-r",
        doc_kind="payroll_run", doc_id=r_id,
        sections=[]))


@bp.get("/leaves")
def leaves():
    return render_template("hr/list.html", **h.ctx(
        "الإجازات", [("الموارد البشرية", None), ("الإجازات", None)], active="hr-e",
        new_url=url_for("web_hr.new_leave"),
        columns=[{"key": "leave_type", "label": "النوع"}, {"key": "days_count", "label": "الأيام", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/hr/leaves", empty="لا طلبات"))


@bp.get("/leaves/new")
def new_leave():
    return render_template("hr/form.html", **h.ctx(
        "طلب إجازة", [("الموارد البشرية", None), ("الإجازات", url_for("web_hr.leaves")), ("جديد", None)],
        active="hr-e", api_post="/api/v1/hr/leaves", redirect_url="/hr/leaves",
        fields=[{"name": "employee_id", "label": "الموظف", "type": "select", "source": "employees", "required": True},
                {"name": "leave_type", "label": "النوع", "type": "select",
                 "options": [("annual", "سنوية"), ("sick", "مرضية"), ("unpaid", "غير مدفوعة")]},
                {"name": "from_date", "label": "من", "type": "date", "required": True},
                {"name": "to_date", "label": "إلى", "type": "date", "required": True},
                {"name": "reason", "label": "السبب", "type": "textarea"}],
        cancel_url=url_for("web_hr.leaves")))


@bp.get("/loans")
def loans():
    return render_template("hr/list.html", **h.ctx(
        "السلف", [("الموارد البشرية", None), ("السلف", None)], active="hr-e",
        new_url=url_for("web_hr.new_loan"),
        columns=[{"key": "amount", "label": "المبلغ", "num": True},
                 {"key": "remaining", "label": "المتبقي", "num": True},
                 {"key": "status", "label": "الحالة", "badge": True}],
        rows=[], api_src="/api/v1/hr/loans", empty="لا سلف"))


@bp.get("/loans/new")
def new_loan():
    return render_template("hr/form.html", **h.ctx(
        "سلفة جديدة", [("الموارد البشرية", None), ("السلف", url_for("web_hr.loans")), ("جديدة", None)],
        active="hr-e", api_post="/api/v1/hr/loans", redirect_url="/hr/loans",
        fields=[{"name": "employee_id", "label": "الموظف", "type": "select", "source": "employees", "required": True},
                {"name": "amount", "label": "المبلغ", "type": "number", "required": True, "ltr": True},
                {"name": "installment", "label": "القسط الشهري", "type": "number", "required": True, "ltr": True},
                {"name": "starts_on", "label": "تبدأ في", "type": "date", "required": True}],
        cancel_url=url_for("web_hr.loans")))
