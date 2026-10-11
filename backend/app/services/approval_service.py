"""ApprovalService — اعتمادات القيود مع فصل المهام (صانع != معتمد).

Flow: request() creates a pending row -> decide() approves/rejects.
Deciding your own entry raises SelfApprovalError. Expiry is enforced.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta
from ..extensions import db
from ..models.journal import EntryApproval, JournalEntry
from .errors import SelfApprovalError, NotFoundError, BadStateError

log = logging.getLogger(__name__)


def request_approval(*, tenant_id: uuid.UUID, entity_id: uuid.UUID, entry_id: uuid.UUID,
                     approver_id: uuid.UUID, level: int = 1, mandatory: bool = True,
                     sla_days: int = 3, actor_id: uuid.UUID) -> EntryApproval:
    entry = db.session.get(JournalEntry, entry_id)
    if entry is None:
        raise NotFoundError("Entry not found")
    if entry.created_by == approver_id:
        raise SelfApprovalError("Maker cannot be the approver")
    row = EntryApproval(tenant_id=tenant_id, entity_id=entity_id, entry_id=entry_id,
                        approver_id=approver_id, status="pending",
                        sequence=level, is_mandatory=mandatory,
                        expires_at=datetime.utcnow() + timedelta(days=sla_days),
                        created_by=actor_id, updated_by=actor_id)
    db.session.add(row)
    entry.status = "pending_review"
    db.session.commit()
    return row


def decide(approval_id: uuid.UUID, *, actor_id: uuid.UUID, approve: bool, reason: str | None = None) -> EntryApproval:
    row = db.session.get(EntryApproval, approval_id)
    if row is None:
        raise NotFoundError("Approval not found")
    if row.status != "pending":
        raise BadStateError(f"Approval is {row.status}")
    if row.approver_id != actor_id:
        from .errors import ForbiddenError
        raise ForbiddenError("Only the assigned approver can decide")
    entry = db.session.get(JournalEntry, row.entry_id)
    if entry and entry.created_by == actor_id:
        raise SelfApprovalError("Maker cannot approve own entry")
    if row.expires_at and row.expires_at < datetime.utcnow():
        row.status = "rejected"
        row.reason = "expired"
    else:
        row.status = "approved" if approve else "rejected"
        row.reason = reason
    row.approved_at = datetime.utcnow()
    if entry and approve:
        entry.status = "approved"
        entry.approved_by = actor_id
        entry.approved_at = datetime.utcnow()
    db.session.commit()
    log.info("approval %s decided=%s by %s", approval_id, row.status, actor_id)
    return row


def check_doc_rule(*, tenant_id, entity_id, doc_type: str, total: float,
                   creator_id, poster_id) -> None:
    """قاعدة الاعتماد بالمبلغ: فوق الحد يتطلب مرحّلًا ثانيًا غير المنشئ."""
    from ..models.biz import ApprovalRule
    rule = (db.session.query(ApprovalRule)
            .filter_by(tenant_id=uuid.UUID(str(tenant_id)),
                       entity_id=uuid.UUID(str(entity_id)),
                       doc_type=doc_type, is_deleted=False)
            .order_by(ApprovalRule.min_amount.desc()).first())
    if rule is None or not rule.is_active or total < float(rule.min_amount):
        return
    if str(creator_id) == str(poster_id):
        raise SelfApprovalError(
            f"Amount {total} requires a second approver (role {rule.required_role})")
