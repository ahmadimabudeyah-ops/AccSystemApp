"""Audit trail helper — append-only. Called by services on sensitive actions."""
from __future__ import annotations
import logging
import uuid
from ..extensions import db
from ..models.project import AuditLog

log = logging.getLogger(__name__)


def record(*, tenant_id, actor_id, action: str, entity_type: str,
           entity_id=None, old=None, new=None, ip: str | None = None) -> None:
    try:
        db.session.add(AuditLog(
            tenant_id=uuid.UUID(str(tenant_id)),
            actor_id=uuid.UUID(str(actor_id)) if actor_id else None,
            action=action, entity_type=entity_type,
            entity_id=uuid.UUID(str(entity_id)) if entity_id else None,
            old_values=old, new_values=new, ip=ip))
        db.session.flush()
    except Exception as exc:  # audit must never break the business flow
        db.session.rollback()
        log.warning("audit failed: %s", exc)
