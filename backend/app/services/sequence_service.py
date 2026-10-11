"""SequenceService — توليد الرقم الرسمي الذري لكل دفتر/سنة.

Mirrors fn_generate_official_number(): row-level lock on the sequence row
so concurrent postings never reuse a number. Gaps are documented, never reused.
"""
from __future__ import annotations
import logging
import uuid
from ..extensions import db
from ..models.journal import Journal, JournalSequence

log = logging.getLogger(__name__)


def next_official_number(*, tenant_id: uuid.UUID, entity_id: uuid.UUID,
                         journal_id: uuid.UUID, fiscal_year_id: uuid.UUID) -> str:
    journal = db.session.get(Journal, journal_id)
    if not journal:
        raise ValueError(f"Journal not found: {journal_id}")
    seq = (
        db.session.query(JournalSequence)
        .filter_by(tenant_id=tenant_id, journal_id=journal_id, fiscal_year_id=fiscal_year_id)
        .with_for_update()
        .first()
    )
    if seq is None:
        seq = JournalSequence(tenant_id=tenant_id, entity_id=entity_id, journal_id=journal_id,
                              fiscal_year_id=fiscal_year_id, last_number=0,
                              prefix=journal.sequence_prefix or journal.code,
                              suffix="", length=journal.sequence_length or 6)
        db.session.add(seq)
        db.session.flush()
    seq.last_number += 1
    number = f"{seq.prefix}-{str(seq.last_number).zfill(seq.length)}{seq.suffix}"
    log.info("sequence journal=%s year=%s -> %s", journal_id, fiscal_year_id, number)
    return number


DOC_PREFIXES = {"cash_txn": "CT", "transfer": "TR", "invoice": "INV", "bill": "BILL",
                "payment": "PAY", "check": "CHK", "return": "RET", "adjustment": "ADJ"}


def next_doc_number(*, tenant_id: uuid.UUID, entity_id: uuid.UUID,
                    doctype: str, year: int | None = None) -> str:
    """رقم مستند رسمي ذري لكل (كيان/نوع/سنة): PREFIX-YYYY-0001."""
    from datetime import date as _date
    from ..models.treasury import DocSequence
    year = year or _date.today().year
    seq = (
        db.session.query(DocSequence)
        .filter_by(tenant_id=tenant_id, entity_id=entity_id, doctype=doctype, year=year)
        .with_for_update()
        .first()
    )
    if seq is None:
        seq = DocSequence(tenant_id=tenant_id, entity_id=entity_id,
                          doctype=doctype, year=year, last_number=0)
        db.session.add(seq)
        db.session.flush()
    seq.last_number += 1
    prefix = DOC_PREFIXES.get(doctype, doctype.upper()[:4])
    return f"{prefix}-{year}-{str(seq.last_number).zfill(4)}"
