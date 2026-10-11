"""PeriodService — الفترات: resolve / lock / reopen.

Mirrors fn_check_period_open(): every posting resolves its period from posting_date.
Soft lock blocks new manual entries but allows adjustments; hard lock blocks all.
Reopen requires an approval row (passed by caller) — never silent.
"""
from __future__ import annotations
import datetime
import logging
import uuid
from ..extensions import db
from ..models.entity import FiscalPeriod
from .errors import NoPeriodError, PeriodClosedError

log = logging.getLogger(__name__)


def resolve(entity_id: uuid.UUID, posting_date: datetime.date) -> FiscalPeriod:
    period = (
        db.session.query(FiscalPeriod)
        .filter(FiscalPeriod.entity_id == entity_id,
                FiscalPeriod.starts_on <= posting_date,
                FiscalPeriod.ends_on >= posting_date,
                FiscalPeriod.is_deleted.is_(False))
        .first()
    )
    if period is None:
        raise NoPeriodError(f"No fiscal period covers {posting_date}")
    return period


def assert_open(period: FiscalPeriod, *, allow_soft: bool = False) -> None:
    if period.status == "hard_closed":
        raise PeriodClosedError(f"Period {period.code} is hard-closed")
    if period.status == "soft_closed" and not allow_soft:
        raise PeriodClosedError(f"Period {period.code} is soft-closed")


def lock(period_id: uuid.UUID, *, hard: bool, actor_id: uuid.UUID, reason: str) -> FiscalPeriod:
    period = db.session.get(FiscalPeriod, period_id)
    if period is None:
        from .errors import NotFoundError
        raise NotFoundError("Period not found")
    period.status = "hard_closed" if hard else "soft_closed"
    from datetime import datetime
    period.status_changed_at = datetime.utcnow()
    period.status_changed_by = actor_id
    db.session.flush()
    log.info("period %s locked hard=%s by %s: %s", period.code, hard, actor_id, reason)
    return period


def reopen(period_id: uuid.UUID, *, actor_id: uuid.UUID, reason: str) -> FiscalPeriod:
    if not reason or len(reason.strip()) < 5:
        raise ValueError("Reopen requires a documented reason")
    period = db.session.get(FiscalPeriod, period_id)
    if period is None:
        from .errors import NotFoundError
        raise NotFoundError("Period not found")
    period.status = "open"
    from datetime import datetime
    period.status_changed_at = datetime.utcnow()
    period.status_changed_by = actor_id
    db.session.flush()
    log.warning("period %s REOPENED by %s: %s", period.code, actor_id, reason)
    return period
