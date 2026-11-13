"""Dashboard summary truth tests.

Covers the accounting contract behind /api/v1/reports/dashboard-summary:
posted-only balances, net revenue/expense after contra accounts, subsidiary
AR/AP accounts, reversal netting to zero, future-dated exclusion, disputed
invoices staying overdue, and entity/tenant protection.
"""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text as _sql

from app.extensions import db
from app.models.tenant import Tenant
from app.models.entity import Entity, FiscalPeriod
from app.models.journal import Journal
from app.models.user import User
from app.services import posting_service, balance_service
from app.services.errors import NotFoundError


@pytest.fixture(scope="module")
def mapp():
    from app import create_app
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture(scope="module")
def mctx(mapp):
    with mapp.app_context():
        tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
        assert tenant, "DEMO tenant missing"
        db.session.execute(_sql("SET app.current_tenant_id = :t"),
                           {"t": str(tenant.id)})
        yield


@pytest.fixture(scope="module")
def run():
    return "D" + uuid.uuid4().hex[:4].upper()


@pytest.fixture(scope="module")
def env(mctx):
    tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
    entity = db.session.query(Entity).filter_by(tenant_id=tenant.id).first()
    journal = db.session.query(Journal).filter_by(
        tenant_id=tenant.id, entity_id=entity.id, code="GEN").first()
    maker = db.session.query(User).filter_by(
        tenant_id=tenant.id, email="admin@demo.local").first()
    checker = db.session.query(User).filter_by(
        tenant_id=tenant.id, email="checker@demo.local").first()
    assert all([tenant, entity, journal, maker, checker])
    return {"tenant": tenant, "entity": entity, "journal": journal,
            "maker": maker.id, "checker": checker.id}


@pytest.fixture(scope="module")
def api(mapp, mctx):
    client = mapp.test_client()
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin@demo.local", "password": "Admin@123"},
                    headers={"X-Tenant-ID": "DEMO"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return {"client": client,
            "headers": {"Authorization": "Bearer " + r.get_json()["access_token"],
                        "X-Tenant-ID": "DEMO"}}


def _summary(env):
    return balance_service.get_dashboard_summary(
        env["entity"].id, env["tenant"].id)


def _mk_account(api, env, code, name, atype, balance):
    body = {"entity_id": str(env["entity"].id), "code": code,
            "name_ar": name, "account_type": atype,
            "normal_balance": balance, "is_postable": True}
    r = api["client"].post("/api/v1/accounts", json=body, headers=api["headers"])
    assert r.status_code == 201, (code, r.status_code, r.get_data(as_text=True)[:400])
    return r.get_json()["data"]


def _hdr(env, key, posting_date):
    return {"tenant_id": env["tenant"].id, "entity_id": env["entity"].id,
            "journal_id": env["journal"].id, "entry_type": "manual",
            "document_date": posting_date, "posting_date": posting_date,
            "currency_id": "JOD", "exchange_rate": 1,
            "source_event_key": key}


def _post(env, key, posting_date, lines):
    entry = posting_service.create_entry(
        _hdr(env, key, posting_date), lines, actor_id=env["maker"])
    return posting_service.post_entry(entry.id, env["checker"])


def _L(acc, debit=0, credit=0):
    return {"account_id": acc["id"], "debit": debit, "credit": credit}


def test_net_revenue_and_expense_after_contra(api, env, run):
    rev = _mk_account(api, env, f"{run}-REV", "إيراد اختبار الداشبورد",
                      "income", "credit")
    ctr = _mk_account(api, env, f"{run}-CTR", "خصم اختبار الداشبورد",
                      "contra_income", "debit")
    exp = _mk_account(api, env, f"{run}-EXP", "مصروف اختبار الداشبورد",
                      "expense", "debit")
    cex = _mk_account(api, env, f"{run}-CEX", "تخفيض مصروف اختبار الداشبورد",
                      "contra_expense", "credit")
    cash = _mk_account(api, env, f"101{run}-CASH", "نقدية اختبار الداشبورد",
                       "asset", "debit")
    ar = _mk_account(api, env, f"1210{run}-RAR", "ذمم اختبار الداشبورد",
                     "asset", "debit")
    base = _summary(env)

    _post(env, f"dash-rev-{run}", date(2026, 11, 2), [
        _L(ar, debit=1000), _L(rev, credit=1000),
    ])
    _post(env, f"dash-ctr-{run}", date(2026, 11, 2), [
        _L(ctr, debit=250), _L(ar, credit=250),
    ])
    _post(env, f"dash-exp-{run}", date(2026, 11, 3), [
        _L(exp, debit=400), _L(cash, credit=400),
    ])
    _post(env, f"dash-cex-{run}", date(2026, 11, 3), [
        _L(cash, debit=100), _L(cex, credit=100),
    ])

    after = _summary(env)
    assert after["gross_revenue"] - base["gross_revenue"] == 1000
    assert after["discounts"] - base["discounts"] == 250
    assert round(after["revenue"] - base["revenue"], 3) == 750
    assert round(after["expenses"] - base["expenses"], 3) == 300
    assert round(after["profit"] - base["profit"], 3) == 450
    assert round(after["cash"] - base["cash"], 3) == -300
    assert round(after["receivables"] - base["receivables"], 3) == 750
    assert round(after["revenue_mix"]["adjustments"]
                 - base["revenue_mix"]["adjustments"], 3) == -250
    assert after["revenue_mix"]["net_revenue"] == after["revenue"]


def test_receivable_and_payable_include_subaccounts(api, env, run):
    ar = _mk_account(api, env, f"1210{run}-AR", "ذمم فرعية اختبار",
                     "asset", "debit")
    ap = _mk_account(api, env, f"2010{run}-AP", "ذمم دائنة فرعية اختبار",
                     "liability", "credit")
    exp = _mk_account(api, env, f"{run}-EXP2", "مصروف ذمم اختبار",
                      "expense", "debit")
    base = _summary(env)

    _post(env, f"dash-ar-{run}", date(2026, 11, 4), [
        _L(ar, debit=321.5), _L(exp, credit=321.5),
    ])
    _post(env, f"dash-ap-{run}", date(2026, 11, 4), [
        _L(exp, debit=123.25), _L(ap, credit=123.25),
    ])

    after = _summary(env)
    assert round(after["receivables"] - base["receivables"], 3) == 321.5
    assert round(after["payables"] - base["payables"], 3) == 123.25


def test_reversed_entry_nets_to_zero(api, env, run):
    rev = _mk_account(api, env, f"{run}-REV2", "إيراد عكس اختبار",
                      "income", "credit")
    cash = _mk_account(api, env, f"101{run}-CASH2", "نقدية عكس اختبار",
                       "asset", "debit")
    base = _summary(env)

    original = _post(env, f"dash-reverse-{run}", date(2026, 11, 5), [
        _L(cash, debit=500), _L(rev, credit=500),
    ])
    posted = _summary(env)
    assert round(posted["revenue"] - base["revenue"], 3) == 500

    posting_service.reverse_entry(
        original.id, reason="اختبار عكس الداشبورد",
        reversal_date=date(2026, 11, 6), user_id=env["checker"])

    after = _summary(env)
    assert round(after["revenue"] - base["revenue"], 3) == 0
    assert round(after["cash"] - base["cash"], 3) == 0


def test_future_dated_entries_are_excluded(api, env, run):
    today = date.today()
    period = db.session.query(FiscalPeriod).filter(
        FiscalPeriod.entity_id == env["entity"].id,
        FiscalPeriod.starts_on > today,
        FiscalPeriod.status == "open",
        FiscalPeriod.is_deleted.is_(False),
    ).order_by(FiscalPeriod.starts_on).first()
    if period is None:
        pytest.skip("no open future fiscal period")

    rev = _mk_account(api, env, f"{run}-REV3", "إيراد مستقبلي اختبار",
                      "income", "credit")
    cash = _mk_account(api, env, f"101{run}-CASH3", "نقدية مستقبلية اختبار",
                       "asset", "debit")
    base = _summary(env)

    _post(env, f"dash-future-{run}", period.starts_on + timedelta(days=1), [
        _L(cash, debit=777), _L(rev, credit=777),
    ])

    after = _summary(env)
    assert round(after["revenue"] - base["revenue"], 3) == 0
    assert round(after["cash"] - base["cash"], 3) == 0


def test_disputed_invoice_stays_overdue(env):
    base = _summary(env)
    if base["overdue_invoices"] < 1:
        pytest.skip("no overdue invoices in seed data")

    row = db.session.execute(_sql(
        "SELECT i.id, i.status, i.doc_number FROM customer_invoices i "
        "JOIN parties p ON p.id = i.customer_id "
        "WHERE p.entity_id = :en AND p.is_deleted = FALSE "
        "AND i.status IN ('posted','partially_paid') AND i.remaining_amount > 0 "
        "AND i.due_on < CURRENT_DATE AND i.is_deleted = FALSE LIMIT 1"),
        {"en": env["entity"].id}).first()
    if row is None:
        pytest.skip("no posted overdue invoice to dispute")

    inv_id, old_status, doc = row
    try:
        db.session.execute(_sql(
            "UPDATE customer_invoices SET status = 'disputed' WHERE id = :id"),
            {"id": inv_id})
        db.session.commit()

        after = _summary(env)
        assert after["overdue_invoices"] == base["overdue_invoices"]
        assert doc in {o["doc"] for o in after["overdue_list"]}
    finally:
        db.session.execute(_sql(
            "UPDATE customer_invoices SET status = :s WHERE id = :id"),
            {"s": old_status, "id": inv_id})
        db.session.commit()


def test_entity_guard_and_api_validation(api, env):
    with pytest.raises(NotFoundError):
        balance_service.get_dashboard_summary(
            env["entity"].id, uuid.uuid4())

    h = api["headers"]
    missing = api["client"].get("/api/v1/reports/dashboard-summary", headers=h)
    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "ENTITY_REQUIRED"

    bad = api["client"].get(
        "/api/v1/reports/dashboard-summary?entity_id=" + str(uuid.uuid4()),
        headers=h)
    assert bad.status_code == 404
    assert bad.get_json()["error"]["code"] == "NOT_FOUND"
