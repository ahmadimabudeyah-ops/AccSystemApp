"""Engine acceptance tests: balance, idempotency, reversal, periods, self-approval.

Run:  pytest tests/test_posting.py -v
Needs: local PG with phase SQL applied + DEMO tenant/entity/period/journal/accounts.
"""
import uuid
from datetime import date

import pytest

from app.extensions import db
from app.models.tenant import Tenant
from app.models.entity import Entity, FiscalYear, FiscalPeriod
from app.models.account import Account
from app.models.journal import Journal
from app.services import posting_service
from app.services.errors import (
    UnbalancedEntryError, DuplicateEventError, ImmutablePostedError,
    SelfApprovalError, PeriodClosedError, AlreadyReversedError,
)


@pytest.fixture()
def env(ctx):
    tenant = db.session.query(Tenant).filter_by(code="DEMO").first()
    assert tenant, "DEMO tenant missing — run seeds"
    entity = db.session.query(Entity).filter_by(tenant_id=tenant.id).first()
    cash = db.session.query(Account).filter_by(tenant_id=tenant.id, entity_id=entity.id, code="101001").first()
    sales = db.session.query(Account).filter_by(tenant_id=tenant.id, entity_id=entity.id, code="4010").first()
    journal = db.session.query(Journal).filter_by(tenant_id=tenant.id, entity_id=entity.id, code="GEN").first()
    assert cash and sales and journal, "seed_engine.py must run first"
    from app.models.user import User
    maker = db.session.query(User).filter_by(tenant_id=tenant.id, email="admin@demo.local").first()
    checker = db.session.query(User).filter_by(tenant_id=tenant.id, email="checker@demo.local").first()
    assert maker and checker, "run scripts/seed_base.py + scripts/mkchecker.py"
    maker, checker = maker.id, checker.id
    period = db.session.query(FiscalPeriod).filter_by(entity_id=entity.id).first()
    return {"tenant": tenant, "entity": entity, "cash": cash, "sales": sales,
            "journal": journal, "maker": maker, "checker": checker, "period": period}


def _header(env, **kw):
    p = env["period"]
    base = {"tenant_id": env["tenant"].id, "entity_id": env["entity"].id,
            "journal_id": env["journal"].id, "entry_type": "manual",
            "document_date": p.starts_on, "posting_date": p.starts_on,
            "currency_id": "JOD", "exchange_rate": 1}
    base.update(kw)
    return base


def _lines(env, amount=100.0):
    return [{"account_id": env["cash"].id, "debit": amount, "credit": 0},
            {"account_id": env["sales"].id, "debit": 0, "credit": amount}]


def test_balanced_entry_posts(env):
    e = posting_service.create_entry(_header(env), _lines(env), actor_id=env["maker"])
    e = posting_service.post_entry(e.id, env["checker"])
    assert e.status == "posted" and e.official_number


def test_unbalanced_rejected(env):
    lines = [{"account_id": env["cash"].id, "debit": 100, "credit": 0},
             {"account_id": env["sales"].id, "debit": 0, "credit": 90}]
    with pytest.raises(UnbalancedEntryError):
        posting_service.create_entry(_header(env), lines, actor_id=env["maker"])


def test_double_post_idempotent(env):
    e = posting_service.create_entry(_header(env), _lines(env, 55), actor_id=env["maker"])
    n1 = posting_service.post_entry(e.id, env["checker"]).official_number
    n2 = posting_service.post_entry(e.id, env["checker"]).official_number
    assert n1 == n2


def test_self_approval_forbidden(env):
    e = posting_service.create_entry(_header(env), _lines(env, 60), actor_id=env["maker"])
    with pytest.raises(SelfApprovalError):
        posting_service.post_entry(e.id, env["maker"])


def test_duplicate_event_key_replays(env):
    key = f"test-{uuid.uuid4()}"
    e1 = posting_service.create_entry(_header(env, source_event_key=key), _lines(env, 70),
                                      actor_id=env["maker"])
    with pytest.raises(DuplicateEventError):
        posting_service.create_entry(_header(env, source_event_key=key), _lines(env, 70),
                                     actor_id=env["maker"])
    assert e1.status == "draft"


def test_full_reversal_once(env):
    e = posting_service.create_entry(_header(env), _lines(env, 80), actor_id=env["maker"])
    posting_service.post_entry(e.id, env["checker"])
    rev = posting_service.reverse_entry(e.id, reason="test reversal",
                                        reversal_date=e.posting_date, user_id=env["checker"])
    assert rev.status == "posted"
    with pytest.raises(AlreadyReversedError):
        posting_service.reverse_entry(e.id, reason="second try",
                                      reversal_date=e.posting_date, user_id=env["checker"])
