"""Chart-of-accounts acceptance (structure & posting guards).

Scope keys: all created codes start with the per-run prefix (rerun-safe);
assertions are scoped to run accounts, never to global totals.
Needs: local PG :5433 with phases + DEMO tenant/entity/period/journals/users.
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
    return "Z" + uuid.uuid4().hex[:4].upper()


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
            "maker": maker.id, "checker": checker.id, "period": period}


@pytest.fixture(scope="module")
def api(mapp, mctx):
    client = mapp.test_client()
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin@demo.local", "password": "Admin@123"},
                    headers={"X-Tenant-ID": "DEMO"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    tok = r.get_json()["access_token"]
    return {"client": client,
            "headers": {"Authorization": f"Bearer {tok}", "X-Tenant-ID": "DEMO"}}


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
def chain(api, env, run):
    sec = _mk(api, env, run, "SEC", "قسم الصناديق", "section")
    gen = _mk(api, env, run, "GEN", "عام الصناديق", "general", sec["id"])
    sub = _mk(api, env, run, "SUB", "مساعد الصناديق", "subsidiary", gen["id"])
    cash = _mk(api, env, run, "CASH", "الصندوق الرئيسي", "detail", sub["id"],
               extra={"control_type": "cash"})
    sub2 = _mk(api, env, run, "SUB2", "الصندوق الفرعي", "detail", sub["id"])
    esec = _mk(api, env, run, "ESEC", "قسم الحقوق", "section", atype="equity", bal="credit")
    egen = _mk(api, env, run, "EGEN", "عام الحقوق", "general", esec["id"], atype="equity", bal="credit")
    esub = _mk(api, env, run, "ESUB", "مساعد الحقوق", "subsidiary", egen["id"], atype="equity", bal="credit")
    eq = _mk(api, env, run, "EQ", "حقوق الملكية", "detail", esub["id"], atype="equity", bal="credit")
    isec = _mk(api, env, run, "ISEC", "قسم الإيرادات", "section", atype="income", bal="credit")
    # إيراد تفصيلي بسلسلة كاملة
    igen = _mk(api, env, run, "IGEN", "عام الإيرادات", "general", isec["id"], atype="income", bal="credit")
    isub = _mk(api, env, run, "ISUB", "مساعد الإيرادات", "subsidiary", igen["id"], atype="income", bal="credit")
    rev = _mk(api, env, run, "REV", "الإيراد", "detail", isub["id"], atype="income", bal="credit")
    xsec = _mk(api, env, run, "XSEC", "قسم المصروفات", "section", atype="expense", bal="debit")
    xgen = _mk(api, env, run, "XGEN", "عام المصروفات", "general", xsec["id"], atype="expense", bal="debit")
    xsub = _mk(api, env, run, "XSUB", "مساعد المصروفات", "subsidiary", xgen["id"], atype="expense", bal="debit")
    exp = _mk(api, env, run, "EXP", "مصروف", "detail", xsub["id"], atype="expense", bal="debit")
    accum = _mk(api, env, run, "ACCUM", "مجمع الإهلاك", "detail", sub["id"],
                atype="contra_asset", bal="credit")
    return {"sec": sec, "gen": gen, "sub": sub, "cash": cash, "sub2": sub2,
            "eq": eq, "rev": rev, "exp": exp, "accum": accum,
            "esec": esec, "isec": isec, "xsec": xsec}


def _hdr(env, run, n, posting_date, **kw):
    h = {"tenant_id": env["tenant"].id, "entity_id": env["entity"].id,
         "journal_id": env["journal"].id, "entry_type": "manual",
         "document_date": posting_date, "posting_date": posting_date,
         "currency_id": "JOD", "exchange_rate": 1,
         "source_event_key": f"chart-test-{run}-{n}"}
    h.update(kw)
    return h


def _L(acc, d=0, c=0):
    return {"account_id": acc["id"], "debit": d, "credit": c}


# ---- 10. creation chain / filters / rejections ---------------------------

def test_10_chain_filters(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    r = c.get(f"/api/v1/accounts?entity_id={eid}&role=detail&q={run}-", headers=h)
    codes = {a["code"] for a in r.get_json()["data"]}
    assert f"{run}-CASH" in codes and f"{run}-SEC" not in codes
    r = c.get(f"/api/v1/accounts?entity_id={eid}&parent_id={chain['sub']['id']}", headers=h)
    assert {a["code"] for a in r.get_json()["data"]} >= {f"{run}-CASH", f"{run}-SUB2"}
    # مرفوض: تفصيلي تحت قسم، وتجميعي قابل للترحيل، وعائلة مخالفة
    bad = [
        {"code": f"{run}-X1", "name_ar": "x", "account_type": "asset",
         "normal_balance": "debit", "hierarchy_role": "detail", "parent_id": chain["sec"]["id"]},
        {"code": f"{run}-X2", "name_ar": "x", "account_type": "asset",
         "normal_balance": "debit", "hierarchy_role": "general",
         "parent_id": chain["sec"]["id"], "is_postable": True},
        {"code": f"{run}-X3", "name_ar": "x", "account_type": "expense",
         "normal_balance": "debit", "hierarchy_role": "general",
         "parent_id": chain["sec"]["id"]},
    ]
    for b in bad:
        b["entity_id"] = eid
        r = c.post("/api/v1/accounts", json=b, headers=h)
        assert r.status_code in (409, 422), (b["code"], r.status_code)


# ---- 12. cycles / cross-entity --------------------------------------------

def test_12_cycles_cross_entity(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    # ربط ذاتي
    r = c.put(f"/api/v1/accounts/{chain['cash']['id']}",
              json={"parent_id": chain["cash"]["id"], "version": chain["cash"]["version"]}, headers=h)
    assert r.status_code in (409, 422)
    # ربط بحفيد (القسم تحت التفصيلي)
    r = c.get(f"/api/v1/accounts/{chain['sec']['id']}", headers=h)
    v = r.get_json()["data"]["version"]
    r = c.put(f"/api/v1/accounts/{chain['sec']['id']}",
              json={"parent_id": chain["cash"]["id"], "version": v}, headers=h)
    assert r.status_code in (409, 422)
    # أب من شركة أخرى (UUID سليم لكيان غير موجود/خارج النطاق)
    import uuid as _u
    r = c.post("/api/v1/accounts",
               json={"entity_id": str(_u.uuid4()), "code": f"{run}-XX", "name_ar": "x",
                     "account_type": "asset", "normal_balance": "debit",
                     "parent_id": chain["cash"]["id"]}, headers=h)
    assert r.status_code in (400, 404, 409, 422)


# ---- 13. concurrent version -------------------------------------------------

def test_13_concurrent_version(api, chain):
    c = api["client"]
    h = api["headers"]
    r = c.get(f"/api/v1/accounts/{chain['gen']['id']}", headers=h)
    v = r.get_json()["data"]["version"]
    r1 = c.put(f"/api/v1/accounts/{chain['gen']['id']}",
               json={"name_ar": "عام الصناديق أ", "version": v}, headers=h)
    r2 = c.put(f"/api/v1/accounts/{chain['gen']['id']}",
               json={"name_ar": "عام الصناديق ب", "version": v}, headers=h)
    assert r1.status_code == 200 and r2.status_code == 409
    assert c.get(f"/api/v1/accounts/{chain['gen']['id']}", headers=h).get_json()["data"]["name_ar"] == "عام الصناديق أ"


# ---- 14. duplicate code ------------------------------------------------------

def test_14_duplicate_code(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    body = {"entity_id": str(env["entity"].id), "code": f"{run}-CASH",
            "name_ar": "تكرار", "account_type": "asset", "normal_balance": "debit",
            "hierarchy_role": "detail", "parent_id": chain["sub"]["id"]}
    r = c.post("/api/v1/accounts", json=body, headers=h)
    assert r.status_code == 409
    from sqlalchemy import text as _t  # القيد الفريد احتياطي على مستوى القاعدة
    cons = db.session.execute(_t(
        "SELECT 1 FROM pg_constraint WHERE conname = 'uq_accounts_code'")).first()
    assert cons is not None  # قيد فريد احتياطي على مستوى القاعدة


# ---- 15. forged source / manual bypass ---------------------------------------

def test_15_forged_source_rejected(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    # حساب رقابي يمنع اليدوي
    ctl = _mk(api, env, run, "CTL", "رقابي", "detail", chain["sub"]["id"],
              extra={"allow_manual": False})
    p = env["period"]
    hdr = {"entity_id": str(env["entity"].id), "journal_id": str(env["journal"].id),
           "document_date": str(p.starts_on), "posting_date": str(p.starts_on),
           "description": "forge", "source_module": "sales",
           "lines": [{"account_id": ctl["id"], "debit": 10, "credit": 0, "manual": False},
                     {"account_id": chain["cash"]["id"], "debit": 0, "credit": 10, "manual": False}]}
    r = c.post("/api/v1/journal-entries", json=hdr, headers=h)
    assert r.status_code in (400, 404, 422), (r.status_code, r.get_data(as_text=True)[:300])
    # والمسار اليدوي العادي مرفوض أيضًا على الرقابي
    hdr2 = dict(hdr, source_module="manual")
    r = c.post("/api/v1/journal-entries", json=hdr2, headers=h)
    assert r.status_code in (400, 404, 422)


# ---- 16. partial-update semantics ---------------------------------------------

def test_16_partial_update(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    aid = chain["sub2"]["id"]
    v0 = c.get(f"/api/v1/accounts/{aid}", headers=h).get_json()["data"]["version"]
    r = c.put(f"/api/v1/accounts/{aid}",
              json={"allow_manual": False, "version": v0}, headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["allow_manual"] is False
    v1 = r.get_json()["data"]["version"]
    r = c.put(f"/api/v1/accounts/{aid}",
              json={"name_en": None, "version": v1}, headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["name_en"] is None
    v2 = r.get_json()["data"]["version"]
    before = c.get(f"/api/v1/accounts/{aid}", headers=h).get_json()["data"]
    r = c.put(f"/api/v1/accounts/{aid}", json={"version": v2}, headers=h)
    after = r.get_json()["data"]
    assert r.status_code == 200 and after["name_ar"] == before["name_ar"]
    # تفصيلي مستخدم لاحقًا؟ هنا غير مستخدم — تغييرhasil مسموح؛ نتحقق من القيمة الفعلية
    assert after["allow_manual"] is False  # False محفوظ لا معامل كغياب


# ---- legacy edit keeps relations / version required / detail parent --------

def test_legacy_edit_keep(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    # زوج قديم يُنشأ داخل الاختبار (لا يعتمد على بذرة معينة)
    r = c.post("/api/v1/accounts",
               json={"entity_id": eid, "code": f"{run}-LEGROOT", "name_ar": f"جذر قديم {run}",
                     "account_type": "asset", "normal_balance": "debit"}, headers=h)
    assert r.status_code == 201
    leg_root = r.get_json()["data"]
    assert leg_root["hierarchy_role"] is None
    r = c.post("/api/v1/accounts",
               json={"entity_id": eid, "code": f"{run}-LEGACY", "name_ar": f"قديم فرعي {run}",
                     "account_type": "asset", "normal_balance": "debit",
                     "parent_id": leg_root["id"]}, headers=h)
    assert r.status_code == 201
    leg = r.get_json()["data"]
    assert leg["hierarchy_role"] is None
    v = leg["version"]
    # تعديل الاسم فقط دون دور/أب — ينجح ويُبقي العلاقة
    r = c.put(f"/api/v1/accounts/{leg['id']}",
              json={"name_ar": f"قديم فرعي معدل {run}", "version": v}, headers=h)
    assert r.status_code == 200
    now = c.get(f"/api/v1/accounts/{leg['id']}", headers=h).get_json()["data"]
    assert now["parent_id"] == leg_root["id"] and now["hierarchy_role"] is None
    # ابن تحت تفصيلي — مرفوض
    r = c.post("/api/v1/accounts",
               json={"entity_id": eid, "code": f"{run}-BADKID", "name_ar": "x",
                     "account_type": "asset", "normal_balance": "debit",
                     "parent_id": chain["cash"]["id"]}, headers=h)
    assert r.status_code in (409, 422)


def test_version_required(api, chain):
    c = api["client"]
    h = api["headers"]
    r = c.put(f"/api/v1/accounts/{chain['sub']['id']}",
              json={"name_ar": "بلا نسخة"}, headers=h)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VERSION_REQUIRED"


def test_tree_full_and_balances(api, env, chain):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    tree = c.get(f"/api/v1/accounts/tree?entity_id={eid}", headers=h).get_json()
    diag = c.get(f"/api/v1/accounts/diagnostics?entity_id={eid}", headers=h).get_json()["data"]
    assert tree["count"] == diag["counts"]["total"]  # الشجرة كاملة بلا حد 50
    assert any(n.get("children") for n in tree["data"])  # متداخلة فعلًا
    b = c.get(f"/api/v1/accounts/{chain['sub']['id']}/balance?mode=aggregate",
              headers=h).get_json()["data"]
    assert b["mode"] == "aggregate" and b["functional_currency"] == "JOD"
    assert b["mixed_currency"] is False


def test_delete_budget_ref(api, env, run, chain):
    from app.models.project import Budget, BudgetLine
    from app.models.entity import FiscalYear
    c = api["client"]
    h = api["headers"]
    fy = db.session.query(FiscalYear).filter_by(entity_id=env["entity"].id).first()
    b = Budget(tenant_id=env["tenant"].id, entity_id=env["entity"].id,
               fiscal_year_id=fy.id, code=f"B-{run}", name_ar="موازنة اختبار",
               created_by=env["maker"], updated_by=env["maker"])
    db.session.add(b)
    db.session.flush()
    db.session.add(BudgetLine(tenant_id=env["tenant"].id, budget_id=b.id,
                              account_id=uuid.UUID(chain["exp"]["id"]),
                              planned_amount=100,
                              created_by=env["maker"], updated_by=env["maker"]))
    db.session.commit()
    try:
        r = c.delete(f"/api/v1/accounts/{chain['exp']['id']}", headers=h)
        assert r.status_code == 409
        assert r.get_json()["error"]["code"] == "REFERENCED"
    finally:
        db.session.query(BudgetLine).filter_by(budget_id=b.id).delete()
        db.session.query(Budget).filter_by(id=b.id).delete()
        db.session.commit()

def test_06_deactivate_blocks_post(api, env, run, chain):
    from app.models.account import Account as _A
    c = api["client"]
    h = api["headers"]
    r = c.post("/api/v1/accounts",
               json={"entity_id": str(env["entity"].id), "code": f"{run}-D6",
                     "name_ar": "للتعطيل", "account_type": "asset",
                     "normal_balance": "debit", "hierarchy_role": "detail",
                     "parent_id": chain["sub"]["id"]}, headers=h)
    assert r.status_code == 201
    acc_id = r.get_json()["data"]["id"]
    p = env["period"]
    e = posting_service.create_entry(
        _hdr(env, run, "d1", p.starts_on),
        [{"account_id": acc_id, "debit": 50, "credit": 0},
         {"account_id": chain["eq"]["id"], "debit": 0, "credit": 50}],
        actor_id=env["maker"])
    acc = db.session.get(_A, acc_id)
    acc.is_active = False
    db.session.commit()
    import pytest as _p
    with _p.raises(Exception):
        posting_service.post_entry(e.id, env["checker"])
    db.session.refresh(e)
    assert e.status == "draft" and not e.official_number  # بلا أثر جزئي
    acc.is_active = True
    db.session.commit()
    e2 = posting_service.post_entry(e.id, env["checker"])
    assert e2.status == "posted"
    bal = balance_service.get_account_balance(uuid.UUID(acc_id))
    assert bal["balance"] == 50.0


# ---- 9. rename keeps balances; locked code change refused -----------------------

def test_09_rename_and_locked_code(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    before = balance_service.get_account_balance(uuid.UUID(chain["cash"]["id"]))
    r = c.get(f"/api/v1/accounts/{chain['cash']['id']}", headers=h)
    v = r.get_json()["data"]["version"]
    r = c.put(f"/api/v1/accounts/{chain['cash']['id']}",
              json={"name_ar": "الصندوق الرئيسي المعدل", "version": v}, headers=h)
    assert r.status_code == 200
    after = balance_service.get_account_balance(uuid.UUID(chain["cash"]["id"]))
    assert before == after
    # رمز مقفل في خدمة (1210) — مرفوض بسبب موثق
    recv = db.session.query(Account).filter_by(
        tenant_id=env["tenant"].id, entity_id=env["entity"].id, code="1210").first()
    rv = recv.version
    r = c.put(f"/api/v1/accounts/{recv.id}", json={"code": "1219", "version": rv}, headers=h)
    assert r.status_code == 409
    msg = r.get_json()["error"].get("message", "")
    assert "1210" in msg or "مبيعات" in msg or "خدمات" in msg or "رمز" in msg


# ---- stats / filters / bulk-status (list redesign) ---------------------------

def test_stats_and_filters(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    eid = str(env["entity"].id)
    s = c.get(f"/api/v1/accounts/stats?entity_id={eid}", headers=h).get_json()["data"]
    assert s["total"] >= 1 and s["details"] >= 1
    assert s["total"] == s["sections"] + s["generals"] + s["subsidiaries"] + s["details"] + s["unclassified"]
    r = c.get(f"/api/v1/accounts?entity_id={eid}&normal_balance=debit&q={run}-", headers=h)
    assert all(a["normal_balance"] == "debit" for a in r.get_json()["data"])
    r = c.get(f"/api/v1/accounts?entity_id={eid}&status=active&page_size=10", headers=h).get_json()
    assert r["page_size"] == 10 and len(r["data"]) <= 10
    r = c.get(f"/api/v1/accounts?entity_id={eid}&page_size=999", headers=h).get_json()
    assert r["page_size"] == 100  # سقف مقصود لا حد أكبر اعتباطًا


def test_bulk_status_guarded(api, env, run, chain):
    c = api["client"]
    h = api["headers"]
    ids = [chain["sub2"]["id"], chain["cash"]["id"], "00000000-0000-0000-0000-000000000000"]
    r = c.post("/api/v1/accounts/bulk-status",
               json={"ids": ids, "is_active": False, "status": "inactive"}, headers=h)
    assert r.status_code == 200
    d = r.get_json()["data"]
    assert (d["ok"], d["failed"]) == (2, 1)
    assert c.get(f"/api/v1/accounts/{chain['cash']['id']}", headers=h).get_json()["data"]["status"] == "inactive"
    # إعادة التفعيل + رفض الدفعة الفارغة/الكبيرة
    r = c.post("/api/v1/accounts/bulk-status",
               json={"ids": [chain["sub2"]["id"], chain["cash"]["id"]],
                     "is_active": True, "status": "active"}, headers=h)
    assert r.get_json()["data"]["failed"] == 0
    assert c.post("/api/v1/accounts/bulk-status", json={"ids": []}, headers=h).status_code == 400
