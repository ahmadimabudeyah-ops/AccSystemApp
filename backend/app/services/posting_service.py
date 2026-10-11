"""PostingService — إنشاء القيود والتحقق والترحيل والعكس.

Mirrors DB triggers so violations surface as clean 4xx errors first:
- validate_balance  <-> trg_je_balance
- validate_accounts <-> trg_jl_guards (postable/active/same-entity)
- validate_period  <-> period lock check
- check_idempotency <-> uq_entry_event / event_keys

Every mutation runs in a transaction with a savepoint; every state change
writes a structured audit log record (logger "audit").
"""
from __future__ import annotations
import hashlib
import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from ..extensions import db
from ..models.account import Account
from ..models.entity import FiscalYear
from ..models.journal import JournalEntry, JournalLine
from . import event_service, period_service, sequence_service
from .errors import (
    UnbalancedEntryError, BadAccountError, DuplicateEventError,
    EventConflictError, ImmutablePostedError, SelfApprovalError,
    BadStateError, NotFoundError, ValidationError,
)

log = logging.getLogger(__name__)
audit = logging.getLogger("audit")


def _uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    """Coerce JSON string ids to UUID (API passes strings; DB needs UUID)."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _content_hash(header: dict, lines: list[dict]) -> str:
    canonical = json.dumps({"h": header, "l": lines}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------- validation

def validate_balance(lines: list[dict]) -> tuple[Decimal, Decimal]:
    """مجموع المدين يجب أن يساوي مجموع الدائن وكل سطر جهة واحدة."""
    total_d = sum(Decimal(str(l.get("debit", 0))) for l in lines)
    total_c = sum(Decimal(str(l.get("credit", 0))) for l in lines)
    if total_d != total_c or total_d <= 0:
        raise UnbalancedEntryError(f"Unbalanced: debit={total_d} credit={total_c}")
    for l in lines:
        d, c = Decimal(str(l.get("debit", 0))), Decimal(str(l.get("credit", 0)))
        if (d > 0) == (c > 0):
            raise UnbalancedEntryError("Each line must carry debit XOR credit")
    return total_d, total_c


def validate_accounts(entity_id: uuid.UUID, lines: list[dict], *, allow_manual_check: bool = True) -> None:
    """الحسابات من نفس الكيان، قابلة للحركة، نشطة."""
    for l in lines:
        acc = db.session.get(Account, l["account_id"])
        if acc is None or acc.is_deleted:
            raise BadAccountError(f"Account not found: {l.get('account_id')}")
        if acc.entity_id != entity_id:
            raise BadAccountError(f"Account belongs to another entity: {acc.code}")
        if not acc.is_postable:
            raise BadAccountError(f"Account is summary-only: {acc.code}")
        if acc.status != "active":
            raise BadAccountError(f"Account is {acc.status}: {acc.code}")
        if allow_manual_check and not acc.allow_manual and l.get("manual", True):
            raise BadAccountError(f"Account disallows manual entries: {acc.code}")


def validate_period(entity_id: uuid.UUID, posting_date: date, *, allow_soft: bool = False):
    """الفترة مشتقة من تاريخ الترحيل ويجب أن تكون مفتوحة."""
    period = period_service.resolve(entity_id, posting_date)
    period_service.assert_open(period, allow_soft=allow_soft)
    return period


def check_idempotency(*, tenant_id: uuid.UUID, entity_id: uuid.UUID,
                      event_key: str, content_hash: str) -> JournalEntry | None:
    """نفس المفتاح + نفس المحتوى -> أعد القيد الأصلي. محتوى مختلف -> تعارض."""
    row = event_service.get_by_key(tenant_id=tenant_id, entity_id=entity_id, event_key=event_key)
    if row is None or row.status != "processed":
        return None
    if (row.extra or {}).get("content_hash") != content_hash:
        raise EventConflictError(f"Event key reused with different content: {event_key}")
    entry = db.session.get(JournalEntry, row.journal_entry_id) if row.journal_entry_id else None
    if entry is None:
        raise EventConflictError(f"Event key points to missing entry: {event_key}")
    return entry


# ---------------------------------------------------------------- create/post

def create_entry(header: dict[str, Any], lines: list[dict],
                 *, actor_id: uuid.UUID, _skip_event_claim: bool = False) -> JournalEntry:
    """إنشاء قيد مسودة مع كل التحققات. ذري عبر savepoint."""
    tenant_id = _uuid(header["tenant_id"])
    entity_id = _uuid(header["entity_id"])
    header = {**header, "tenant_id": tenant_id, "entity_id": entity_id,
              "journal_id": _uuid(header["journal_id"]),
              "source_document_id": _uuid(header.get("source_document_id"))}
    posting_date = header["posting_date"]
    event_key = header.get("source_event_key")
    content_hash = _content_hash(header, lines)
    lines = [{**l, "account_id": _uuid(l["account_id"]),
              "branch_id": _uuid(l.get("branch_id")),
              "partner_id": _uuid(l.get("partner_id"))} for l in lines]

    if event_key and not _skip_event_claim:
        replay = check_idempotency(tenant_id=tenant_id, entity_id=entity_id,
                                   event_key=event_key, content_hash=content_hash)
        if replay is not None:
            log.info("idempotent replay event_key=%s entry=%s", event_key, replay.id)
            raise DuplicateEventError(f"Replayed: {event_key}")

    validate_balance(lines)
    validate_accounts(entity_id, lines)
    period = validate_period(entity_id, posting_date)
    total_d, total_c = validate_balance(lines)

    savepoint = db.session.begin_nested()
    try:
        entry = JournalEntry(
            tenant_id=tenant_id, entity_id=entity_id, journal_id=header["journal_id"],
            entry_type=header.get("entry_type", "manual"),
            document_date=header.get("document_date", posting_date), posting_date=posting_date,
            period_id=period.id, description=header.get("description"),
            reference=header.get("reference"), source_module=header.get("source_module", "manual"),
            source_document_id=header.get("source_document_id"), source_event_key=event_key,
            source_version=header.get("source_version", 1),
            currency_id=header.get("currency_id", "JOD"),
            exchange_rate=header.get("exchange_rate", 1),
            total_debit=total_d, total_credit=total_c, status="draft",
            created_by=actor_id, updated_by=actor_id,
        )
        db.session.add(entry)
        db.session.flush()
        for i, l in enumerate(lines, 1):
            debit = Decimal(str(l.get("debit", 0)))
            credit = Decimal(str(l.get("credit", 0)))
            ex = Decimal(str(l.get("exchange_rate", header.get("exchange_rate", 1))))
            db.session.add(JournalLine(
                tenant_id=tenant_id, entity_id=entity_id, entry_id=entry.id, line_number=i,
                account_id=l["account_id"], debit=debit, credit=credit,
                currency_id=l.get("currency_id", header.get("currency_id", "JOD")),
                amount_currency=l.get("amount_currency", float(debit or credit)),
                exchange_rate=ex, amount_functional=(debit or credit) * ex,
                partner_id=l.get("partner_id"), due_date=l.get("due_date"),
                branch_id=l.get("branch_id"), dimensions=l.get("dimensions", {}),
                description=l.get("description"), source_line_ref=l.get("source_line_ref"),
                created_by=actor_id, updated_by=actor_id,
            ))
        if event_key and not _skip_event_claim:
            row = event_service.claim(
                tenant_id=tenant_id, entity_id=entity_id,
                source_module=header.get("source_module", "manual"),
                source_document_id=header.get("source_document_id") or entry.id,
                event_type=header.get("event_type", f"{header.get('source_module', 'manual')}.created"),
                event_version=header.get("source_version", 1),
                event_key=event_key, actor_id=actor_id,
            )
            row.extra = {"content_hash": content_hash}
            event_service.complete(row, entry.id)
        savepoint.commit()
    except Exception:
        savepoint.rollback()
        raise
    db.session.commit()
    audit.info("entry.created id=%s tenant=%s entity=%s actor=%s total=%s",
               entry.id, tenant_id, entity_id, actor_id, total_d)
    return entry


def post_entry(entry_id: uuid.UUID, user_id: uuid.UUID,
               expected_version: int | None = None) -> JournalEntry:
    """ترحيل القيد: رقم رسمي ذري + حالة POSTED + تدقيق. المرحّل خالد.

    فصل المهام: القيود *اليدوية* تتطلب مرحّلًا غير الصانع. القيود المولدة
    آليًا من مستند تجاري معتمد (source_module != manual) يرحّلها نفس المستخدم
    لأن الضبط تم على المستند نفسه (سياسة موثقة في DELIVERY.md).
    """
    entry = db.session.get(JournalEntry, entry_id, with_for_update=True)
    if entry is None or entry.is_deleted:
        raise NotFoundError("Entry not found")
    if entry.status == "posted":
        return entry  # idempotent
    if entry.status not in ("draft", "approved"):
        raise BadStateError(f"Cannot post from {entry.status}")
    if expected_version is not None and entry.version != expected_version:
        raise BadStateError("Entry was modified concurrently")
    if entry.created_by == user_id and entry.source_module == "manual":
        raise SelfApprovalError("Maker cannot post own entry")
    validate_period(entry.entity_id, entry.posting_date)

    year_code = str(entry.posting_date.year)
    year = db.session.query(FiscalYear).filter_by(entity_id=entry.entity_id, code=year_code).first()
    if year is None:
        raise NotFoundError(f"Fiscal year {year_code} not found")
    entry.official_number = sequence_service.next_official_number(
        tenant_id=entry.tenant_id, entity_id=entry.entity_id,
        journal_id=entry.journal_id, fiscal_year_id=year.id)
    entry.status = "posted"
    entry.status_changed_at = datetime.utcnow()
    entry.status_changed_by = user_id
    entry.posted_at = datetime.utcnow()
    entry.posted_by = user_id
    entry.updated_by = user_id
    db.session.commit()
    audit.info("entry.posted id=%s official=%s actor=%s", entry.id, entry.official_number, user_id)
    from . import audit_service as _audit_svc
    _audit_svc.record(tenant_id=entry.tenant_id, actor_id=user_id, action="post",
                      entity_type="journal_entries", entity_id=entry.id,
                      new={"official_number": entry.official_number, "status": "posted"})
    db.session.commit()
    return entry


def reverse_entry(entry_id: uuid.UUID, reason: str, reversal_date: date,
                  user_id: uuid.UUID, event_key: str | None = None) -> JournalEntry:
    """عكس القيد عبر ReversalService (تفادي الاستيراد الدائري)."""
    from . import reversal_service
    return reversal_service.reverse_full(entry_id, reason=reason,
                                         reversal_date=reversal_date,
                                         actor_id=user_id, event_key=event_key)


def partial_adjustment(entry_id: uuid.UUID, amount, account_id: uuid.UUID,
                        user_id: uuid.UUID, side: str = "debit",
                        description: str | None = None) -> JournalEntry:
    """تسوية جزئية عبر ReversalService."""
    from . import reversal_service
    return reversal_service.partial_adjustment(entry_id, amount=Decimal(str(amount)),
                                               account_id=account_id, side=side,
                                               actor_id=user_id, description=description)
