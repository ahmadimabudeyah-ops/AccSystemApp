"""Realistic demo seeds: payroll accounts, brackets, employees, student, project, budget."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.entity import Entity, FiscalYear  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.hr import Employee, IncomeTaxBracket  # noqa: E402
from app.models.party import Party  # noqa: E402
from app.models.edu import Student, Guardian  # noqa: E402
from app.models.project import Project, Budget, BudgetLine  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    t = db.session.query(Tenant).filter_by(code="DEMO").first()
    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": str(t.id)})
    e = db.session.query(Entity).filter_by(tenant_id=t.id, code="MAIN").first()
    admin = db.session.query(User).filter_by(tenant_id=t.id, email="admin@demo.local").first()

    def one(model, filt, **kw):
        row = db.session.query(model).filter_by(**filt).first()
        if row is None:
            row = model(**kw)
            db.session.add(row)
            db.session.flush()
        return row

    for code, ar in [("2151", "الضمان الاجتماعي المستحق"), ("2160", "ضريبة الدخل المستحقة")]:
        one(Account, {"tenant_id": t.id, "entity_id": e.id, "code": code},
            tenant_id=t.id, entity_id=e.id, code=code, name_ar=ar,
            account_type="liability", normal_balance="credit", is_postable=True,
            created_by=admin.id, updated_by=admin.id)
    for lo, hi, rate in [(0, 5000, 5), (5000, 10000, 10), (10000, 15000, 15), (15000, None, 20)]:
        if not db.session.query(IncomeTaxBracket).filter_by(
                tenant_id=t.id, year=2026, from_amount=lo).first():
            db.session.add(IncomeTaxBracket(tenant_id=t.id, year=2026, from_amount=lo,
                                            to_amount=hi, rate=rate,
                                            created_by=admin.id, updated_by=admin.id))
    for no, name, basic, housing, trans in [
            ("E-001", "أحمد محمد الخالدي", 800, 100, 50),
            ("E-002", "سارة عبدالله الناصر", 1200, 150, 75),
            ("E-003", "خالد يوسف العتيبي", 650, 80, 40)]:
        one(Employee, {"tenant_id": t.id, "entity_id": e.id, "employee_no": no},
            tenant_id=t.id, entity_id=e.id, employee_no=no, full_name_ar=name,
            national_id="99" + no[-4:] + "00000", hire_date=date(2024, 1, 15),
            basic_salary=basic, housing_allowance=housing, transport_allowance=trans,
            status="active", created_by=admin.id, updated_by=admin.id)
    gparty = one(Party, {"tenant_id": t.id, "entity_id": e.id, "code": "G-001"},
                 tenant_id=t.id, entity_id=e.id, code="G-001", name_ar="ولي أمر تجريبي",
                 status="active", created_by=admin.id, updated_by=admin.id)
    guardian = one(Guardian, {"tenant_id": t.id, "full_name_ar": "ولي أمر تجريبي"},
                   tenant_id=t.id, party_id=gparty.id, full_name_ar="ولي أمر تجريبي",
                   phone="+962790000001", created_by=admin.id, updated_by=admin.id)
    sparty = one(Party, {"tenant_id": t.id, "entity_id": e.id, "code": "ST-001"},
                 tenant_id=t.id, entity_id=e.id, code="ST-001", name_ar="طالب تجريبي",
                 status="active", created_by=admin.id, updated_by=admin.id)
    one(Student, {"tenant_id": t.id, "entity_id": e.id, "student_no": "ST-001"},
        tenant_id=t.id, entity_id=e.id, party_id=sparty.id, student_no="ST-001",
        full_name_ar="طالب تجريبي", grade_level="السابع", academic_year="2026",
        status="active", created_by=admin.id, updated_by=admin.id)
    proj = one(Project, {"tenant_id": t.id, "entity_id": e.id, "code": "PRJ-001"},
               tenant_id=t.id, entity_id=e.id, code="PRJ-001", name_ar="مشروع تجريبي",
               budget_total=50000, status="active", created_by=admin.id, updated_by=admin.id)
    fy = db.session.query(FiscalYear).filter_by(tenant_id=t.id, entity_id=e.id, code="2026").first()
    budget = one(Budget, {"tenant_id": t.id, "entity_id": e.id, "code": "BUD-2026"},
                 tenant_id=t.id, entity_id=e.id, fiscal_year_id=fy.id, code="BUD-2026",
                 name_ar="موازنة 2026", status="approved", created_by=admin.id, updated_by=admin.id)
    for code, planned in [("5110", 120000), ("5120", 24000), ("4010", 300000)]:
        acc = db.session.query(Account).filter_by(tenant_id=t.id, entity_id=e.id, code=code).first()
        if acc and not db.session.query(BudgetLine).filter_by(budget_id=budget.id, account_id=acc.id).first():
            db.session.add(BudgetLine(tenant_id=t.id, budget_id=budget.id, account_id=acc.id,
                                      planned_amount=planned, created_by=admin.id, updated_by=admin.id))
    db.session.commit()
    print("SEED2_OK")
