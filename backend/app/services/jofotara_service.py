"""JoFotara e-invoicing client skeleton (sandbox-ready, needs production credentials).

Production wiring: set JOFOTARA_BASE_URL + JOFOTARA_API_KEY env, implement
_sign() with the issued certificate, then flip SANDBOX=False. Queue processor:
read einvoicing_queue(queued) -> build payload -> POST -> store response ->
accepted/rejected + retry with backoff (attempts column).
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import uuid
from sqlalchemy import text as _text
from ..extensions import db

log = logging.getLogger(__name__)
SANDBOX = os.getenv("JOFOTARA_SANDBOX", "1") == "1"


def build_payload(*, invoice_no: str, issue_date: str, seller_tax_id: str,
                  buyer_tax_id: str | None, lines: list[dict],
                  totals: dict, currency: str = "JOD") -> dict:
    items = [{"description": l.get("description", ""), "quantity": float(l.get("qty", 0)),
              "unit_price": float(l.get("unit_price", 0)),
              "tax_rate": float(l.get("tax_rate", 0) or 0),
              "line_total": float(l.get("line_total", 0))} for l in lines]
    payload = {"invoice_no": invoice_no, "issue_date": issue_date,
               "currency": currency, "seller_tax_id": seller_tax_id,
               "buyer_tax_id": buyer_tax_id, "items": items,
               "subtotal": totals.get("subtotal", 0), "tax_total": totals.get("tax_total", 0),
               "grand_total": totals.get("grand_total", 0),
               "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"jo:{invoice_no}"))}
    payload["qr_content"] = f"JO|{seller_tax_id}|{invoice_no}|{payload['grand_total']}|{payload['uuid']}"
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def submit(payload: dict) -> dict:
    """Send to JoFotara. Sandbox NEVER reports production acceptance."""
    if SANDBOX:
        log.info("jofotara sandbox submit %s", payload["invoice_no"])
        return {"status": "sandbox_accepted", "external_ref": "SBX-" + payload["uuid"][:8],
                "payload_hash": payload["digest"],
                "note": "sandbox simulation — not a government acceptance"}
    raise NotImplementedError("Configure JOFOTARA_BASE_URL/API_KEY + signing certificate")


def process_queue(*, tenant_id=None, limit: int = 20) -> list[dict]:
    """معالجة الطابور: بناء الحمولة + إرسال + تحديث الحالة + عد المحاولات."""
    from ..extensions import db
    from ..models.sales import CustomerInvoice
    out = []
    q = db.session.execute(_text(
        "SELECT id, invoice_id FROM einvoicing_queue "
        "WHERE einv_status IN ('queued','retrying') AND is_deleted = FALSE "
        + ("AND tenant_id = :t " if tenant_id else "") + "ORDER BY created_at LIMIT :n"),
        {**( {"t": str(tenant_id)} if tenant_id else {}), "n": limit}).all()
    for qid, inv_id in q:
        inv = db.session.get(CustomerInvoice, uuid.UUID(str(inv_id)))
        if inv is None:
            continue
        from ..models.party import Party as _Party
        from ..models.biz import Tax as _Tax
        buyer = db.session.get(_Party, inv.customer_id) if inv.customer_id else None
        seller_tax = os.getenv("JOFOTARA_SELLER_TAX_ID", "") or "UNCONFIGURED"

        def _rate(line):
            tid = getattr(line, "tax_id", None)
            if not tid:
                return 0
            t = db.session.get(_Tax, tid)
            return float(t.rate) if t else 0

        lines = [{"description": l.description, "qty": float(l.qty),
                  "unit_price": float(l.unit_price),
                  "tax_rate": _rate(l),
                  "line_total": float(l.line_total)} for l in inv.lines if not l.is_deleted]
        payload = build_payload(
            invoice_no=inv.doc_number, issue_date=inv.invoice_date.isoformat(),
            seller_tax_id=seller_tax,
            buyer_tax_id=getattr(buyer, "tax_id", None),
            lines=lines,
            totals={"subtotal": float(inv.subtotal), "tax_total": float(inv.tax_total),
                    "grand_total": float(inv.grand_total)}, currency=inv.currency_id)
        try:
            resp = submit(payload)
            db.session.execute(_text(
                "UPDATE einvoicing_queue SET einv_status = :s, attempts = attempts + 1, "
                "sent_at = now(), responded_at = now(), response_payload = :r::jsonb "
                "WHERE id = :i"),
                {"s": resp["status"], "r": json.dumps(resp), "i": str(qid)})
            out.append({"queue_id": str(qid), "status": resp["status"]})
        except Exception as exc:  # noqa: BLE001 — queue must survive sender bugs
            db.session.execute(_text(
                "UPDATE einvoicing_queue SET einv_status = 'retrying', attempts = attempts + 1, "
                "last_error = :e WHERE id = :i"), {"e": str(exc)[:500], "i": str(qid)})
            out.append({"queue_id": str(qid), "status": "retrying"})
    db.session.commit()
    return out
