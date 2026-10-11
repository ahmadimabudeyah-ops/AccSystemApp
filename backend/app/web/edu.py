"""Education web pages."""
from flask import Blueprint, render_template, redirect, url_for, flash
from . import _helpers as h

bp = Blueprint("web_edu", __name__, url_prefix="/education")

STU_COLS = [{"key": "student_no", "label": "الرقم"}, {"key": "full_name_ar", "label": "الاسم"},
            {"key": "grade_level", "label": "الصف"}, {"key": "status", "label": "الحالة", "badge": True}]
FEE_COLS = [{"key": "student", "label": "الطالب"}, {"key": "academic_year", "label": "العام"},
            {"key": "net_fees", "label": "الصافي", "num": True}, {"key": "status", "label": "الحالة", "badge": True}]


@bp.get("/students")
def students():
    return render_template("education/list.html", **h.ctx(
        "الطلاب", [("التعليم", None), ("الطلاب", None)], active="edu-s",
        new_url=url_for("web_edu.new_student"), columns=STU_COLS, rows=[],
        api_src="/api/v1/education/students", empty="لا طلاب"))


@bp.get("/students/new")
def new_student():
    return render_template("education/form.html", **h.ctx(
        "طالب جديد", [("التعليم", None), ("الطلاب", url_for("web_edu.students")), ("جديد", None)],
        active="edu-s", api_post="/api/v1/education/students", redirect_url="/education/students",
        fields=[{"name": "student_no", "label": "الرقم", "required": True, "ltr": True},
                {"name": "full_name_ar", "label": "الاسم", "required": True},
                {"name": "grade_level", "label": "الصف"}],
        cancel_url=url_for("web_edu.students")))


@bp.get("/fee-contracts")
def contracts():
    return render_template("education/list.html", **h.ctx(
        "عقود الرسوم", [("التعليم", None), ("الرسوم", None)], active="edu-f",
        new_url=url_for("web_edu.new_contract"), columns=FEE_COLS, rows=[],
        api_src="/api/v1/education/fee-contracts", empty="لا عقود",
        row_actions=True, detail_base="/education/fee-contracts"))


@bp.get("/fee-contracts/new")
def new_contract():
    return render_template("education/form.html", **h.ctx(
        "عقد رسوم", [("التعليم", None), ("الرسوم", url_for("web_edu.contracts")), ("جديد", None)],
        active="edu-f", api_post="/api/v1/education/fee-contracts", redirect_url="/education/fee-contracts",
        fields=[{"name": "student_id", "label": "الطالب", "type": "select", "source": "students", "required": True},
                {"name": "academic_year", "label": "العام الدراسي", "value": "2026", "ltr": True},
                {"name": "total_fees", "label": "الإجمالي", "type": "number", "required": True, "ltr": True},
                {"name": "discount_pct", "label": "الخصم %", "type": "number", "ltr": True},
                {"name": "installments", "label": "عدد الأقساط", "type": "number", "value": 4, "ltr": True}],
        cancel_url=url_for("web_edu.contracts")))


@bp.get("/fee-contracts/<uuid:c_id>")
def contract_detail(c_id):
    return render_template("education/detail.html", **h.ctx(
        "تفاصيل العقد", [("التعليم", None), ("الرسوم", url_for("web_edu.contracts")), ("التفاصيل", None)],
        active="edu-f",
        doc_kind="fee_contract", doc_id=c_id,
        sections=[]))
