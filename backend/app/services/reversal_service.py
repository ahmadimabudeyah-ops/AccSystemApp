"""ReversalService — العكس الكامل مرة واحدة + التسوية الجزئية.

Full reversal: new entry with mirrored lines (debit<->credit), same amounts
(no repricing), posting_date >= original, linked via ReversalLink.
Partial: adjustment entry linked to the original without flipping its status.
"""
from __future__ import annotations
import logging
import uuid
from datetime import date
from decimal import Decimal
from ..extensions import db
from ..models.journal import JournalEntry, JournalLine, ReversalLink
from .errors import NotFoundError, BadStateError, AlreadyReversedError, ValidationError
from . import period_service

log = logging.getLogger(__name__)


def reverse_full(entry_id: uuid.UUID, *, reason: str, reversal_date: date,
                 actor_id: uuid.UUID, event_key: str | None = None) -> JournalEntry:
    original = db.session.get(JournalEntry, entry_id)
    if original is None:
        raise NotFoundError("Entry not found")
    if original.is_reversed:
        raise AlreadyReversedError("Entry already reversed")
    if original.status != "posted":
        raise BadStateError("Only posted entries can be reversed")
    if not reason or len(reason.strip()) < 5:
        raise ValidationError("Reversal reason is required")
    if reversal_date < original.posting_date:
        raise ValidationError("Reversal date must be >= original posting date")
    period_service.assert_open(period_service.resolve(original.entity_id, reversal_date), allow_soft=True)

    from . import posting_service
    if event_key:
        from . import event_service as _ev
        prior = _ev.get_by_key(tenant_id=original.tenant_id, entity_id=original.entity_id,
                               event_key=event_key)
        if prior is not None and prior.status == "processed" and prior.journal_entry_id:
            existing = db.session.get(JournalEntry, prior.journal_entry_id)
            if existing is not None:
                return existing
    mirrored = [
        {"account_id": l.account_id, "debit": float(l.credit), "credit": float(l.debit)}
        for l in original.lines if not l.is_deleted
    ]
    rev = posting_service.create_entry(
        {"tenant_id": original.tenant_id, "entity_id": original.entity_id,
         "journal_id": original.journal_id, "entry_type": "reversal",
         "document_date": reversal_date, "posting_date": reversal_date,
         "description": f"Reversal of {original.official_number or original.id}: {reason}",
         "source_module": "reversal", "source_document_id": original.id,
         "source_event_key": event_key, "currency_id": original.currency_id,
         "exchange_rate": float(original.exchange_rate)},
        mirrored, actor_id=actor_id,
    )
    rev.reversal_of_id = original.id
    from . import sequence_service as _seq
    from ..models.entity import FiscalYear as _FY
    _year = db.session.query(_FY).filter_by(
        entity_id=original.entity_id, code=str(reversal_date.year)).first()
    if _year is None:
        raise NotFoundError(f"Fiscal year {reversal_date.year} not found")
    rev.official_number = _seq.next_official_number(
        tenant_id=original.tenant_id, entity_id=original.entity_id,
        journal_id=original.journal_id, fiscal_year_id=_year.id)
    rev.status = "posted"
    from datetime import datetime
    rev.posted_by = actor_id
    rev.posted_at = datetime.utcnow()
    original.is_reversed = True
    original.status = "reversed"
    original.status_changed_by = actor_id
    from datetime import datetime as _dt
    original.reversed_at = _dt.utcnow()
    original.reversed_by = actor_id
    db.session.add(ReversalLink(tenant_id=original.tenant_id, entity_id=original.entity_id,
                                original_entry_id=original.id, reversal_entry_id=rev.id,
                                reversal_date=reversal_date, reason=reason, reversed_by=actor_id,
                                reversal_type="full",
                                amount_reversed=float(original.total_debit),
                                fiscal_period_id=rev.period_id,
                                created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    log.info("reversed %s -> %s", original.id, rev.id)
    from . import audit_service as _audit_svc
    _audit_svc.record(tenant_id=original.tenant_id, actor_id=actor_id, action="reverse",
                      entity_type="journal_entries", entity_id=original.id,
                      new={"reversal_entry_id": str(rev.id), "reason": reason})
    db.session.commit()
    return rev


def partial_adjustment(entry_id: uuid.UUID, *, amount: Decimal, account_id: uuid.UUID,
                       side: str, actor_id: uuid.UUID, description: str | None = None) -> JournalEntry:
    """تسوية جزئية: قيد تعديل مرتبط بالأصل دون قلبه."""
    original = db.session.get(JournalEntry, entry_id)
    if original is None:
        raise NotFoundError("Entry not found")
    if original.status != "posted":
        raise BadStateError("Only posted entries can be adjusted")
    if side not in ("debit", "credit"):
        raise ValidationError("side must be debit|credit")
    from . import posting_service
    counterpart = original.lines[0].account_id if original.lines else account_id
    lines = [
        {"account_id": account_id, "debit": float(amount) if side == "debit" else 0,
         "credit": float(amount) if side == "credit" else 0},
        {"account_id": counterpart, "debit": float(amount) if side == "credit" else 0,
         "credit": float(amount) if side == "debit" else 0},
    ]
    adj = posting_service.create_entry(
        {"tenant_id": original.tenant_id, "entity_id": original.entity_id,
         "journal_id": original.journal_id, "entry_type": "adjustment",
         "document_date": date.today(), "posting_date": date.today(),
         "description": description or f"Partial adjustment of {original.official_number or original.id}",
         "source_module": "adjustment", "source_document_id": original.id,
         "currency_id": original.currency_id},
        lines, actor_id=actor_id,
    )
    db.session.add(ReversalLink(tenant_id=original.tenant_id, entity_id=original.entity_id,
                                original_entry_id=original.id, reversal_entry_id=adj.id,
                                reversal_date=date.today(), reason=description or "partial adjustment",
                                reversed_by=actor_id, reversal_type="partial",
                                amount_reversed=float(amount),
                                fiscal_period_id=adj.period_id,
                                created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return adj
