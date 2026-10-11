"""EventService — سجل مفاتيح الأحداث: claim / complete / fail / lookup.

Flow: claim() INSERTs the key first (ON CONFLICT -> DuplicateEventError).
On success complete() links the resulting entry. On error fail() records it
for retry with retry_count. get_by_key() lets interrupted callers resume.
"""
from __future__ import annotations
import logging
import uuid
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models.journal import EventKey
from .errors import DuplicateEventError, EventConflictError

log = logging.getLogger(__name__)


def claim(*, tenant_id: uuid.UUID, entity_id: uuid.UUID, source_module: str,
          source_document_id: uuid.UUID, event_type: str, event_version: int = 1,
          event_key: str, actor_id: uuid.UUID) -> EventKey:
    row = EventKey(tenant_id=tenant_id, entity_id=entity_id, source_module=source_module,
                   source_document_id=source_document_id, event_type=event_type,
                   event_version=event_version, event_key=event_key, status="pending",
                   created_by=actor_id, updated_by=actor_id)
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        existing = get_by_key(tenant_id=tenant_id, entity_id=entity_id, event_key=event_key)
        if existing is None:
            raise
        log.info("duplicate event_key=%s status=%s", event_key, existing.status)
        raise DuplicateEventError(f"Event already seen: {event_key}") from exc
    return row


def complete(row: EventKey, journal_entry_id: uuid.UUID) -> EventKey:
    row.status = "processed"
    row.journal_entry_id = journal_entry_id
    from datetime import datetime
    row.processed_at = datetime.utcnow()
    db.session.flush()
    return row


def fail(row: EventKey, error: str) -> EventKey:
    row.status = "failed"
    row.retry_count = (row.retry_count or 0) + 1
    row.last_error = error[:2000]
    db.session.flush()
    return row


def get_by_key(*, tenant_id: uuid.UUID, entity_id: uuid.UUID, event_key: str) -> EventKey | None:
    return (
        db.session.query(EventKey)
        .filter_by(tenant_id=tenant_id, entity_id=entity_id, event_key=event_key, is_deleted=False)
        .first()
    )
