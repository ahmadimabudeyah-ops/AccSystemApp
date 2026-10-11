"""Tenant provisioning: new organization online in one call (trial included).

Creates: tenant + trial subscription + admin + roles/grants + entity/branch +
fiscal year/periods + COA + journals + currencies + taxes + payment terms.
Idempotent by tenant code (returns existing). All-or-nothing transaction.
"""
from __future__ import annotations
import calendar
import importlib.util
import logging
import os
import uuid
from datetime import date, timedelta
from ..extensions import db
from ..models.tenant import Tenant, Plan
from ..models.user import User, Role, Permission, RolePermission
from ..models.entity import Entity, Branch, FiscalYear, FiscalPeriod
from ..models.account import Account
from ..models.journal import Journal
from ..models.treasury import Currency, Tax
from ..models.sales import PaymentTerm
from ..utils.security import hash_password, validate_password
from .errors import ValidationError

log = logging.getLogger(__name__)
TRIAL_DAYS = 30


def _coa_deck():
    """Reuse the canonical IFRS deck from scripts/seed_engine.py (single source)."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed_engine.py")
    spec = importlib.util.spec_from_file_location("_seed_engine_deck", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.COA, mod.JOURNALS


def _rbac_matrix():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed_rbac.py")
    spec = importlib.util.spec_from_file_location("_seed_rbac", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MATRIX, mod.ROLE_NAMES


def provision(*, code: str, name_ar: str, admin_email: str, admin_password: str,
              country: str = "JO", with_demo: bool = False) -> dict:
    code = (code or "").strip().upper()
    if not code or len(code) < 2:
        raise ValidationError("Tenant code required")
    validate_password(admin_password)
    existing = db.session.query(Tenant).filter_by(code=code, is_deleted=False).first()
    if existing:
        return {"tenant_id": str(existing.id), "code": existing.code, "existing": True}
    year = date.today().year
    tenant = Tenant(code=code, name_ar=name_ar.strip(), status="active",
                    default_currency="JOD", country=country)
    db.session.add(tenant)
    db.session.flush()
    from sqlalchemy import text as _text
    db.session.execute(_text("SET LOCAL \"app.current_tenant_id\" = :t"), {"t": str(tenant.id)})
    admin = User(tenant_id=tenant.id, username="admin",
                 email=admin_email.strip().lower(),
                 password_hash=hash_password(admin_password), is_active=True)
    db.session.add(admin)
    db.session.flush()
    admin.created_by = admin.id
    admin.updated_by = admin.id
    # roles + full matrix
    matrix, names = _rbac_matrix()
    catalog = {p.code: p for p in db.session.query(Permission).all()}
    roles = {}
    for rcode, rname in names.items():
        r = Role(tenant_id=tenant.id, code=rcode, name_ar=rname,
                 created_by=admin.id, updated_by=admin.id)
        db.session.add(r)
        db.session.flush()
        roles[rcode] = r
        want = matrix[rcode]
        want = list(catalog.keys()) if want == ["*"] else want
        for pc in want:
            if pc in catalog:
                db.session.add(RolePermission(tenant_id=tenant.id, role_id=r.id,
                                              permission_id=catalog[pc].id,
                                              created_by=admin.id, updated_by=admin.id))
    from ..models.user import UserRole
    db.session.add(UserRole(tenant_id=tenant.id, user_id=admin.id,
                            role_id=roles["TENANT_ADMIN"].id,
                            created_by=admin.id, updated_by=admin.id))
    # entity + branch
    entity = Entity(tenant_id=tenant.id, code="MAIN", name_ar="الكيان الرئيسي",
                    functional_currency="JOD", created_by=admin.id, updated_by=admin.id)
    db.session.add(entity)
    db.session.flush()
    db.session.add(Branch(tenant_id=tenant.id, entity_id=entity.id, code="HQ",
                          name_ar="الفرع الرئيسي", created_by=admin.id, updated_by=admin.id))
    # fiscal year + 12 open periods
    fy = FiscalYear(tenant_id=tenant.id, entity_id=entity.id, code=str(year),
                    name_ar=f"السنة المالية {year}",
                    starts_on=date(year, 1, 1), ends_on=date(year, 12, 31), status="open",
                    created_by=admin.id, updated_by=admin.id)
    db.session.add(fy)
    db.session.flush()
    for m in range(1, 13):
        last = calendar.monthrange(year, m)[1]
        db.session.add(FiscalPeriod(
            tenant_id=tenant.id, entity_id=entity.id, fiscal_year_id=fy.id,
            code=f"{year}-{m:02d}", period_number=m, name_ar=f"فترة {year}-{m:02d}",
            starts_on=date(year, m, 1), ends_on=date(year, m, last), status="open",
            created_by=admin.id, updated_by=admin.id))
    # chart of accounts + journals (canonical deck)
    coa, journals = _coa_deck()

    def _insert(nodes, parent_id=None):
        for c, ar, en, typ, normal, postable, children in nodes:
            acc = Account(tenant_id=tenant.id, entity_id=entity.id, code=c, name_ar=ar,
                          name_en=en, parent_id=parent_id, account_type=typ,
                          normal_balance=normal, is_postable=postable,
                          created_by=admin.id, updated_by=admin.id)
            db.session.add(acc)
            db.session.flush()
            _insert(children, acc.id)
    _insert(coa)
    for jcode, jname, jtype, prefix in journals:
        db.session.add(Journal(tenant_id=tenant.id, entity_id=entity.id, code=jcode,
                               name=jname, type=jtype, sequence_prefix=prefix,
                               sequence_length=6, created_by=admin.id, updated_by=admin.id))
    # currencies, taxes, terms
    for ccode, ar, _en, dec in [("JOD", "دينار أردني", "", 3), ("USD", "دولار أمريكي", "", 2),
                                ("EUR", "يورو", "", 2), ("SAR", "ريال سعودي", "", 2),
                                ("AED", "درهم إماراتي", "", 2)]:
        db.session.add(Currency(tenant_id=tenant.id, code=ccode, name_ar=ar,
                                decimals=dec, created_by=admin.id, updated_by=admin.id))
    db.session.add(Tax(tenant_id=tenant.id, entity_id=entity.id, code="VAT16",
                       name_ar="ضريبة المبيعات 16%", rate=16,
                       created_by=admin.id, updated_by=admin.id))
    db.session.add(PaymentTerm(tenant_id=tenant.id, entity_id=entity.id, code="NET30",
                               name_ar="30 يوم", days=30, is_default=True,
                               created_by=admin.id, updated_by=admin.id))
    # trial subscription (basic plan or first available)
    plan = db.session.query(Plan).filter_by(code="basic", is_deleted=False).first()
    if plan is None:
        plan = db.session.query(Plan).filter_by(is_deleted=False).first()
    if plan:
        from ..models.tenant import Subscription
        db.session.add(Subscription(
            tenant_id=tenant.id, plan_id=plan.id, starts_on=date.today(),
            ends_on=date.today() + timedelta(days=TRIAL_DAYS), status="trial",
            created_by=admin.id, updated_by=admin.id))
    db.session.commit()
    log.info("provisioned tenant %s", code)
    return {"tenant_id": str(tenant.id), "code": code, "existing": False,
            "trial_days": TRIAL_DAYS, "login": admin.email}
