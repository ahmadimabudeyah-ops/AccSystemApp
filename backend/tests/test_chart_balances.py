"""Chart-of-accounts acceptance (balances, reports, subsidiary matching).

Companion to test_chart_levels.py — builds its own run-scoped chart so both
files stay independent and rerun-safe.
"""
import uuid
from datetime import date

import pytest

from app.extensions import db
from app.models.tenant import Tenant
from app.models.entity import Entity, FiscalPeriod
from app.models.account import Account
from app.models.journal import Journal, JournalLine
from app.models.user import User
from app.services import posting_service, balance_service
from app.services.errors import ReportConfigError


@pytest.fixture(scope="module")
def mapp():
    from app import create_app
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture(scope="module")
def mctx(mapp):
    with mapp.app_context():
        from sqlalchemy import text as _t
        tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
        assert tenant, "DEMO tenant missing"
        db.session.execute(_t("SET app.current_tenant_id = :t"), {"t": str(tenant.id)})
        yield


@pytest.fixture(scope="module")
def run():
    return "W" + uuid.uuid4().hex[:4].upper()


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
    period = db.session.query(FiscalPeriod).filter_by(
        entity_id=entity.id, code="2026-01").first()
    assert all([tenant, entity, journal, maker, checker, period])
    return {"tenant": tenant, "entity": entity, "journal": journal,
            "maker": maker.id, "checker": checker.id, "period": period,
            "d0": date(2026, 1, 5), "d1": date(2026, 1, 12),
            "d2": date(2026, 1, 18), "d3": date(2026, 1, 20)}


@pytest.fixture(scope="module")
def api(mapp, mctx):
    client = mapp.test_client()
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin@demo.local", "password": "Admin@123"},
                    headers={"X-Tenant-ID": "DEMO"})
    assert r.status_code == 200
    return {"client": client,
            "headers": {"Authorization": "Bearer " + r.get_json()["access_token"],
                        "X-Tenant-ID": "DEMO"}}


def _mk(api, env, run, code, name, role, parent=None, atype="asset",
        bal="debit", extra=None):
    body = {"entity_id": str(env["entity"].id), "code": f"{run}-{code}",
            "name_ar": name, "account_type": atype, "normal_balance": bal}
    if role:
        body["hierarchy_role"] = role
    if parent:
        body["parent_id"] = str(parent)
    body.update(extra or {})
    r = api["client"].post("/api/v1/accounts", json=body, headers=api["headers"])
    assert r.status_code == 201, (code, r.status_code, r.get_data(as_text=True)[:400])
    return r.get_json()["data"]


@pytest.fixture(scope="module")
def ch(api, env, run):
    sec = _mk(api, env, run, "SEC", "قسم", "section")
    gen = _mk(api, env, run, "GEN", "عام", "general", sec["id"])
    sub = _mk(api, env, run, "SUB", "مساعد", "subsidiary", gen["id"])
    cash = _mk(api, env, run, "CASH", "الرئيسي", "detail", sub["id"],
               extra={"control_type": "cash"})
    sub2 = _mk(api, env, run, "SUB2", "الفرعي", "detail", sub["id"])
    esec = _mk(api, env, run, "ESEC", "قسم حق", "section", atype="equity", bal="credit")
    egen = _mk(api, env, run, "EGEN", "عام حق", "general", esec["id"], atype="equity", bal="credit")
    esub = _mk(api, env, run, "ESUB", "مساعد حق", "subsidiary", egen["id"], atype="equity", bal="credit")
    eq = _mk(api, env, run, "EQ", "حقوق", "detail", esub["id"], atype="equity", bal="credit")
    isec = _mk(api, env, run, "ISEC", "قسم إيراد", "section", atype="income", bal="credit")
    igen = _mk(api, env, run, "IGEN", "عام إيراد", "general", isec["id"], atype="income", bal="credit")
    isub = _mk(api, env, run, "ISUB", "مساعد إيراد", "subsidiary", igen["id"], atype="income", bal="credit")
    rev = _mk(api, env, run, "REV", "إيراد", "detail", isub["id"], atype="income", bal="credit")
    xsec = _mk(api, env, run, "XSEC", "قسم مصروف", "section", atype="expense", bal="debit")
    xgen = _mk(api, env, run, "XGEN", "عام مصروف", "general", xsec["id"], atype="expense", bal="debit")
    xsub = _mk(api, env, run, "XSUB", "مساعد مصروف", "subsidiary", xgen["id"], atype="expense", bal="debit")
    exp = _mk(api, env, run, "EXP", "مصروف", "detail", xsub["id"], atype="expense", bal="debit")
    return {"sec": sec, "gen": gen, "sub": sub, "cash": cash, "sub2": sub2,
            "eq": eq, "rev": rev, "exp": exp}


def _hdr(env, run, n, d, **kw):
    h = {"tenant_id": env["tenant"].id, "entity_id": env["entity"].id,
         "journal_id": env["journal"].id, "entry_type": "manual",
         "document_date": d, "posting_date": d, "currency_id": "JOD",
         "exchange_rate": 1, "source_event_key": f"chart-bal-{run}-{n}"}
    h.update(kw)
    return h


def _L(acc, d=0, c=0):
    return {"account_id": acc["id"], "debit": d, "credit": c}


def _post(env, hdr, lines):
    e = posting_service.create_entry(hdr, lines, actor_id=env["maker"])
    return posting_service.post_entry(e.id, env["checker"])


@pytest.fixture(scope="module")
def movements(env, run, ch):
    d0, d1, d2, d3 = env["d0"], env["d1"], env["d2"], env["d3"]
    a = _post(env, _hdr(env, run, "a", d0), [_L(ch["cash"], d=1000), _L(ch["eq"], c=1000)])
    b = _post(env, _hdr(env, run, "b", d1), [_L(ch["cash"], d=200), _L(ch["rev"], c=200)])
    c_ = _post(env, _hdr(env, run, "c", d2), [_L(ch["exp"], d=150), _L(ch["cash"], c=150)])
    d = _post(env, _hdr(env, run, "d", d3), [_L(ch["sub2"], d=300), _L(ch["eq"], c=300)])
    return {"a": a, "b": b, "c": c_, "d": d}


def _bal(acc_id, **kw):
    return balance_service.get_account_balance(uuid.UUID(acc_id), **kw)


# ---- §14 core numerics --------------------------------------------------------

def test_core_direct_balances(env, ch, movements):
    d0, d1, d3 = env["d0"], env["d1"], env["d3"]
    cash_open = _bal(ch["cash"]["id"], as_of=d0)
    assert (cash_open["debit"], cash_open["credit"]) == (1000.0, 0.0)
    led = balance_service.get_ledger(uuid.UUID(ch["cash"]["id"]), d1, d3)
    assert led["opening_balance"] == 1000.0
    assert [(l["debit"], l["credit"]) for l in led["lines"]] == [(200.0, 0.0), (0.0, 150.0)]
    assert led["closing_balance"] == 1050.0
    s2 = _bal(ch["sub2"]["id"])
    assert (s2["debit"], s2["credit"], s2["balance"]) == (300.0, 0.0, 300.0)


def test_core_aggregate_group(env, ch, movements):
    d0, d3 = env["d0"], env["d3"]
    g_now = _bal(ch["sub"]["id"], mode="aggregate")
    assert (g_now["debit"], g_now["credit"], g_now["balance"]) == (1500.0, 150.0, 1350.0)
    g_open = _bal(ch["sub"]["id"], as_of=d0, mode="aggregate")
    assert (g_open["debit"], g_open["credit"]) == (1000.0, 0.0)
    g_end = _bal(ch["sub"]["id"], as_of=d3, mode="aggregate")
    assert (g_end["debit"] - g_open["debit"], g_end["credit"] - g_open["credit"]) == (500.0, 150.0)
    assert g_now["functional_currency"] == "JOD" and g_now["mixed_currency"] is False


def test_core_trial_and_closing(env, ch, movements):
    tb = balance_service.get_trial_balance(env["period"].id)
    mine = {l["account_id"]: l for l in tb["lines"]
            if l["account_id"] in {ch[k]["id"] for k in ("cash", "sub2", "eq", "rev", "exp")}}
    assert len(mine) == 5
    assert sum(v["debit"] for v in mine.values()) == 1650.0
    assert sum(v["credit"] for v in mine.values()) == 1650.0
    # فترة الحركة وحدها (ب/ج/د): مدين 650 دائن 650
    per = {"cash": (200.0, 150.0), "sub2": (300.0, 0.0), "eq": (0.0, 300.0),
           "rev": (0.0, 200.0), "exp": (150.0, 0.0)}
    for k, (d, c) in per.items():
        full = mine[ch[k]["id"]]
        if k == "cash":
            assert (full["debit"] - 1000.0, full["credit"]) == (d, c)
        elif k == "eq":
            assert (full["debit"], full["credit"] - 1000.0) == (d, c)
        else:
            assert (full["debit"], full["credit"]) == (d, c)
    # صفوف الآباء للعرض فقط + الإجمالي من الفريد
    tb2 = balance_service.get_trial_balance(env["period"].id, with_parents=True)
    assert tb2["total_debit"] == sum(l["debit"] for l in tb2["lines"])
    assert all(p.get("display_only") for p in tb2.get("parent_rows", []))
    # الختام: مدينة 1350+150، دائنة 1300+200، الإجمالي 1500/1500
    assert mine[ch["cash"]["id"]]["debit"] - mine[ch["cash"]["id"]]["credit"] == 1050.0
    assert mine[ch["exp"]["id"]]["debit"] - mine[ch["exp"]["id"]]["credit"] == 150.0
    assert mine[ch["eq"]["id"]]["credit"] - mine[ch["eq"]["id"]]["debit"] == 1300.0
    assert mine[ch["rev"]["id"]]["credit"] - mine[ch["rev"]["id"]]["debit"] == 200.0
    pl = balance_service.get_income_statement(env["period"].id)
    assert pl["lines"]  # smoke: نقطة القوائم تعمل
    # صافي الفترة لنطاق الاختبار حصرًا (النطاق العام ملوث ببيانات سابقة — لا يُدعى عليه)
    my_rev = mine[ch["rev"]["id"]]
    my_exp = mine[ch["exp"]["id"]]
    assert (my_rev["credit"] - my_rev["debit"]) - (my_exp["debit"] - my_exp["credit"]) == 50.0


# ---- 1. contra presentation ----------------------------------------------------

def test_01_contra_net(api, env, run, ch):
    # أصل مدين 1000 ومجمع إهلاك مقابل دائن 200 في نفس العائلة: صافي العرض 800
    acc = _mk(api, env, run, "ACCASS", "أصل", "detail", ch["sub"]["id"])
    accum = _mk(api, env, run, "ACCUM", "مجمع الإهلاك", "detail", ch["sub"]["id"],
                atype="contra_asset", bal="credit")
    _post(env, _hdr(env, run, "contra1", env["d1"]),
          [{"account_id": acc["id"], "debit": 1000, "credit": 0},
           {"account_id": ch["eq"]["id"], "debit": 0, "credit": 1000}])
    _post(env, _hdr(env, run, "contra2", env["d2"]),
          [{"account_id": ch["eq"]["id"], "debit": 200, "credit": 0},
           {"account_id": accum["id"], "debit": 0, "credit": 200}])
    bs = balance_service.get_balance_sheet(env["period"].id)
    buckets = {l["line_code"]: l["amount"] for l in bs["lines"]}
    tb = {l["account_id"]: l for l in
          balance_service.get_trial_balance(env["period"].id)["lines"]}
    a = tb[acc["id"]]
    m = tb[accum["id"]]
    assert (a["debit"] - a["credit"]) + (m["debit"] - m["credit"]) == 800.0
    assert buckets.get("BS.ASSETS", 0) >= 800.0  # دون قلب الإشارة مرتين


# ---- 2/3. foreign currency once + rate freeze ------------------------------------

def test_02_fx_once_and_frozen(env, run, ch):
    d = env["d1"]
    e = posting_service.create_entry(
        _hdr(env, run, "fx", d, currency_id="USD", exchange_rate=0.710),
        [{"account_id": ch["cash"]["id"], "debit": 100, "credit": 0,
          "currency_id": "USD", "exchange_rate": 0.710},
         {"account_id": ch["eq"]["id"], "debit": 0, "credit": 100,
          "currency_id": "USD", "exchange_rate": 0.710}],
        actor_id=env["maker"])
    e = posting_service.post_entry(e.id, env["checker"])
    lines = db.session.query(JournalLine).filter_by(entry_id=e.id).all()
    for l in lines:
        assert float(l.amount_functional) == 71.0  # مرة واحدة فقط
        assert float(l.amount_currency) == 100.0
    scope = balance_service.get_account_balance(uuid.UUID(ch["cash"]["id"]), mode="direct")
    assert scope["mixed_currency"] is True  # تحذير صريح لا رقم مختلط صامت
    # تغيير سعر الجدول لاحقًا لا يغير المرحل (آمن لإعادة التشغيل: تنظيف أولًا)
    from app.models.biz import ExchangeRate
    from sqlalchemy import text as _t
    db.session.execute(_t(
        "DELETE FROM exchange_rates WHERE tenant_id = :t AND from_currency = 'USD' "
        "AND to_currency = 'JOD' AND source = 'test'"),
        {"t": str(env["tenant"].id)})
    db.session.commit()
    db.session.add(ExchangeRate(tenant_id=env["tenant"].id, from_currency="USD",
                                to_currency="JOD", rate=0.9, rate_date=date(2026, 1, 25),
                                source="test",
                                created_by=env["maker"], updated_by=env["maker"]))
    db.session.commit()
    again = db.session.query(JournalLine).filter_by(entry_id=e.id).all()
    assert [float(l.amount_functional) for l in again] == [71.0, 71.0]


# ---- 5. reversal across report dates ----------------------------------------------

def test_05_reversal_keeps_prior_report(env, run, ch):
    from datetime import date as _d
    d_early, d_late = _d(2026, 1, 6), _d(2026, 1, 22)
    e = _post(env, _hdr(env, run, "revt", d_early),
              [_L(ch["sub2"], d=1000), _L(ch["eq"], c=1000)])
    assert _bal(ch["sub2"]["id"], as_of=_d(2026, 1, 10))["balance"] == 1000.0
    rev = posting_service.reverse_entry(e.id, reason="تصحيح معتمد للاختبار",
                                        reversal_date=d_late, user_id=env["checker"])
    assert rev.status == "posted"
    assert _bal(ch["sub2"]["id"], as_of=_d(2026, 1, 10))["balance"] == 1000.0  # السابق ثابت
    cur = _bal(ch["sub2"]["id"])
    assert cur["debit"] - cur["credit"] == 300.0  # 1300 - 1000 (الصافي بعد العكس)


# ---- 7. legacy direct lines + children counted once ---------------------------------

def test_07_legacy_once(api, env, run):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    r = c.post("/api/v1/accounts", json={"entity_id": eid, "code": f"{run}-LEG",
               "name_ar": "قديم", "account_type": "asset", "normal_balance": "debit"},
               headers=h)
    assert r.status_code == 201
    leg = r.get_json()["data"]
    before_code, before_path = leg["code"], leg["path"]
    _post(env, _hdr(env, run, "leg1", env["d1"]),
          [{"account_id": leg["id"], "debit": 500, "credit": 0},
           {"account_id": _eq_id(api, env, run), "debit": 0, "credit": 500}])
    r = c.post("/api/v1/accounts", json={"entity_id": eid, "code": f"{run}-LEGK",
               "name_ar": "قديم فرعي", "account_type": "asset", "normal_balance": "debit",
               "parent_id": leg["id"]}, headers=h)
    assert r.status_code == 201
    kid = r.get_json()["data"]
    _post(env, _hdr(env, run, "leg2", env["d2"]),
          [{"account_id": kid["id"], "debit": 100, "credit": 0},
           {"account_id": _eq_id(api, env, run), "debit": 0, "credit": 100}])
    agg = _bal(leg["id"], mode="aggregate")
    assert (agg["debit"], agg["credit"]) == (600.0, 0.0)  # كل سطر مرة واحدة
    now = c.get(f"/api/v1/accounts/{leg['id']}", headers=h).get_json()["data"]
    assert (now["code"], now["path"]) == (before_code, before_path)  # بلا تغيير أصلي


def _eq_id(api, env, run):
    r = api["client"].get(
        f"/api/v1/accounts?entity_id={env['entity'].id}&q={run}-EQ", headers=api["headers"])
    rows = [a for a in r.get_json()["data"] if a["code"] == f"{run}-EQ"]
    if rows:
        return rows[0]["id"]
    body = {"entity_id": str(env["entity"].id), "code": f"{run}-EQ", "name_ar": "حقوق",
            "account_type": "equity", "normal_balance": "credit"}
    return api["client"].post("/api/v1/accounts", json=body, headers=api["headers"]).get_json()["data"]["id"]


# ---- 4/18. sales invoice + collection + purchase bill ----------------------------------

def test_04_invoice_collect_matching(env, run, ch):
    from app.models.party import Party
    from app.models.product import Product
    import app.services.sales_service as ss
    cust = db.session.query(Party).filter_by(tenant_id=env["tenant"].id).first()
    prod = db.session.query(Product).filter_by(tenant_id=env["tenant"].id).first()
    assert cust and prod
    inv = ss.create_invoice(tenant_id=env["tenant"].id, entity_id=env["entity"].id,
                            customer_id=cust.id, invoice_date=env["d1"],
                            lines=[{"product_id": prod.id, "qty": 1, "unit_price": 100}],
                            actor_id=env["maker"])
    assert float(inv.grand_total) == 100.0
    inv = ss.post_invoice(inv.id, actor_id=env["checker"])
    pay = ss.create_payment(tenant_id=env["tenant"].id, entity_id=env["entity"].id,
                            customer_id=cust.id, pay_date=env["d2"], amount=40,
                            actor_id=env["maker"])
    pay = ss.post_payment(pay.id, cash_account_id=uuid.UUID(ch["cash"]["id"]),
                          actor_id=env["checker"])
    pay = ss.allocate(payment_id=pay.id,
                      allocations=[{"invoice_id": inv.id, "allocated_amount": 40}],
                      actor_id=env["maker"])
    db.session.refresh(inv)
    assert float(inv.remaining_amount) == 60.0
    # أثر الأستاذ: 1210 مدين 100 ودائن 40 — بلا تسجيل مزدوج
    recv = db.session.query(Account).filter_by(
        tenant_id=env["tenant"].id, entity_id=env["entity"].id, code="1210").first()
    inv_lines = db.session.query(JournalLine).filter_by(entry_id=inv.journal_entry_id).all()
    pay_lines = db.session.query(JournalLine).filter_by(entry_id=pay.journal_entry_id).all()
    r_inv = sum(float(l.debit) - float(l.credit) for l in inv_lines if l.account_id == recv.id)
    r_pay = sum(float(l.debit) - float(l.credit) for l in pay_lines if l.account_id == recv.id)
    assert (r_inv, r_pay) == (100.0, -40.0)


def test_18_purchase_bill_posts(env, run):
    from app.models.party import Party
    from app.models.product import Product
    import app.services.purchases_service as ps
    sup = db.session.query(Party).filter_by(tenant_id=env["tenant"].id).first()
    prod = db.session.query(Product).filter_by(tenant_id=env["tenant"].id).first()
    bill = ps.create_bill(tenant_id=env["tenant"].id, entity_id=env["entity"].id,
                          supplier_id=sup.id, bill_date=env["d1"],
                          lines=[{"product_id": prod.id, "qty": 1, "unit_price": 50}],
                          actor_id=env["maker"])
    bill = ps.post_bill(bill.id, actor_id=env["checker"])
    assert bill.status == "posted" and bill.journal_entry_id is not None


# ---- 11. 120+ accounts ------------------------------------------------------------------

def test_11_many_accounts(api, env, run, ch):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    for i in range(120):
        r = c.post("/api/v1/accounts",
                   json={"entity_id": eid, "code": f"{run}-M{i:03d}", "name_ar": f"صنف {i}",
                         "account_type": "asset", "normal_balance": "debit",
                         "hierarchy_role": "detail", "parent_id": ch["sub"]["id"]}, headers=h)
        assert r.status_code == 201, (i, r.status_code)
    r = c.get(f"/api/v1/accounts?entity_id={eid}&parent_id={ch['sub']['id']}&page=3", headers=h)
    assert r.get_json()["total"] >= 122 and len(r.get_json()["data"]) > 0
    r = c.get(f"/api/v1/accounts/search?entity_id={eid}&q={run}-M119", headers=h)
    found = r.get_json()["data"]
    assert found and found[0]["ancestors"]  # المطابق مع سلسلة الأسلاف
    r = c.get(f"/api/v1/accounts/tree?entity_id={eid}", headers=h)
    assert r.get_json()["count"] >= 120


# ---- 17. upgrade parity --------------------------------------------------------------------

def test_17_upgrade_parity(env, run, ch):
    from app.services import chart_service as _cs
    tb1 = balance_service.get_trial_balance(env["period"].id)
    n1 = db.session.query(Account).filter_by(is_deleted=False).count()
    for root in (ch["sec"]["id"],):
        _cs.rebuild_closure(uuid.UUID(root))
    db.session.commit()
    tb2 = balance_service.get_trial_balance(env["period"].id)
    n2 = db.session.query(Account).filter_by(is_deleted=False).count()
    assert n1 == n2 and tb1["total_debit"] == tb2["total_debit"]
    assert tb1["total_credit"] == tb2["total_credit"]


# ---- 19. empty aggregate ----------------------------------------------------------------------

def test_19_empty_aggregate(api, env, run, ch):
    c = api["client"]
    h = api["headers"]
    r = c.post("/api/v1/accounts",
               json={"entity_id": str(env["entity"].id), "code": f"{run}-EMPTY",
                     "name_ar": "فارغ", "account_type": "asset", "normal_balance": "debit",
                     "hierarchy_role": "subsidiary", "parent_id": ch["gen"]["id"]}, headers=h)
    assert r.status_code == 201
    empty = r.get_json()["data"]
    b = _bal(empty["id"], mode="aggregate")
    assert (b["debit"], b["credit"], b["balance"]) == (0.0, 0.0, 0.0)
    with pytest.raises(Exception):
        _post(env, _hdr(env, run, "empty", env["d1"]),
              [{"account_id": empty["id"], "debit": 5, "credit": 0},
               {"account_id": ch["eq"]["id"], "debit": 0, "credit": 5}])


# ---- 20. mapping conflict -----------------------------------------------------------------------

def test_20_mapping_conflict(env, run, ch):
    from sqlalchemy import text as _t
    t, e = str(env["tenant"].id), str(env["entity"].id)
    db.session.execute(_t(
        "INSERT INTO account_report_mappings "
        "(tenant_id, entity_id, account_id, report_code, line_code, sign, created_by, updated_by) "
        "VALUES (:t, :e, :a, 'BS', 'BS.CASH', 'plus', :u, :u)"),
        {"t": t, "e": e, "a": ch["sub"]["id"], "u": str(env["maker"])})
    db.session.execute(_t(
        "INSERT INTO account_report_mappings "
        "(tenant_id, entity_id, account_id, report_code, line_code, sign, created_by, updated_by) "
        "VALUES (:t, :e, :a, 'BS', 'BS.OTHER', 'plus', :u, :u)"),
        {"t": t, "e": e, "a": ch["cash"]["id"], "u": str(env["maker"])})
    db.session.commit()
    try:
        with pytest.raises(ReportConfigError):
            balance_service.get_balance_sheet(env["period"].id)
    finally:
        from sqlalchemy import bindparam as _bp
        db.session.execute(_t(
            "DELETE FROM account_report_mappings WHERE tenant_id = :t AND report_code = 'BS' "
            "AND account_id IN :ids").bindparams(_bp("ids", expanding=True)),
            {"t": t, "ids": [ch["sub"]["id"], ch["cash"]["id"]]})
        db.session.commit()
    bs = balance_service.get_balance_sheet(env["period"].id)
    assert bs["lines"]


# ---- regression: the three logic fixes -----------------------------------------

def test_r1_sales_tax_rate_fallback(env, ch):
    """F1: compute_totals يقبل tax_rate صريحًا بدون tax_id (مطابق للمشتريات)."""
    from app.models.party import Party
    from app.models.product import Product
    from app.models.treasury import Tax
    import app.services.sales_service as ss
    cust = db.session.query(Party).filter_by(tenant_id=env["tenant"].id).first()
    prod = db.session.query(Product).filter_by(tenant_id=env["tenant"].id).first()
    tax = db.session.query(Tax).filter_by(tenant_id=env["tenant"].id, is_active=True).first()
    if tax is None:
        tax = Tax(tenant_id=env["tenant"].id, code="VAT16R", name_ar="ضريبة 16",
                  rate=16, is_active=True, created_by=env["maker"], updated_by=env["maker"])
        db.session.add(tax)
        db.session.commit()
    # tax_rate فقط بلا tax_id — كان يُحسب صفرًا ضريبة قبل الإصلاح
    inv = ss.create_invoice(
        tenant_id=env["tenant"].id, entity_id=env["entity"].id, customer_id=cust.id,
        invoice_date=env["d1"],
        lines=[{"product_id": prod.id, "qty": 2, "unit_price": 100, "tax_rate": 16}],
        actor_id=env["maker"])
    assert float(inv.tax_total) == 32.0
    assert float(inv.grand_total) == 232.0
    # tax_id تُرجّح على tax_rate المرسل
    inv2 = ss.create_invoice(
        tenant_id=env["tenant"].id, entity_id=env["entity"].id, customer_id=cust.id,
        invoice_date=env["d1"],
        lines=[{"product_id": prod.id, "qty": 1, "unit_price": 100,
                "tax_id": tax.id, "tax_rate": 99}],
        actor_id=env["maker"])
    assert float(inv2.tax_total) == 16.0


def test_r2_purchase_tax_to_line_account(env, ch):
    """F2: ضريبة المشتريات تُصنَّف على حساب البند لا على المخزون الافتراضي 1310."""
    from sqlalchemy import text as _t
    from app.models.party import Party
    from app.models.product import Product
    import app.services.purchases_service as ps
    sup = db.session.query(Party).filter_by(tenant_id=env["tenant"].id).first()
    prod = db.session.query(Product).filter_by(tenant_id=env["tenant"].id).first()
    bill = ps.create_bill(
        tenant_id=env["tenant"].id, entity_id=env["entity"].id, supplier_id=sup.id,
        bill_date=env["d1"],
        lines=[{"product_id": prod.id, "qty": 1, "unit_price": 100, "tax_rate": 16,
                "account_id": ch["exp"]["id"]}],  # حساب مصروف مخصص لا المخزون
        actor_id=env["maker"])
    bill = ps.post_bill(bill.id, actor_id=env["checker"])
    rows = db.session.execute(_t(
        "SELECT a.code, l.debit, l.credit FROM journal_lines l "
        "JOIN accounts a ON a.id=l.account_id WHERE l.entry_id=:e"),
        {"e": str(bill.journal_entry_id)}).fetchall()
    by = {r[0]: (float(r[1]), float(r[2])) for r in rows}
    exp_code = db.session.get(Account, ch["exp"]["id"]).code
    assert by[exp_code][0] == 100.0          # صافي البند فقط لا 116
    assert by["2141"][0] == 16.0             # ضريبة المدخلات مدينة على 2141
    assert by.get("1310", (0, 0))[1] == 0.0  # بلا إرجاع خاطئ للمخزون الافتراضي
    assert by["2010"][1] == 116.0            # المورد دائن بالمجموع الكلي
    assert abs(sum(v[0] for v in by.values()) - sum(v[1] for v in by.values())) < 0.001


def test_r3_balance_sheet_cumulative_equation(env, ch, movements):
    """F3: الميزانية تراكمية حتى نهاية الفترة، والجدول المحاسبي متوازن."""
    bs = balance_service.get_balance_sheet(env["period"].id)
    assert bs["basis"] == "cumulative"
    b = {l["line_code"]: l["amount"] for l in bs["lines"]}
    a, li = b.get("BS.ASSETS", 0.0), b.get("BS.LIABILITIES", 0.0)
    eq, ce = b.get("BS.EQUITY", 0.0), b.get("BS.CURRENT_EARNINGS", 0.0)
    # أصول = التزامات + حقوق ملكية + أرباح تراكمية غير مرحّلة
    assert abs(a - (li + eq + ce)) < 0.05
    # قائمة الدخل تبقى حصرًا حركة الفترة الواحدة
    pl = balance_service.get_income_statement(env["period"].id)
    assert pl["basis"] == "period"
