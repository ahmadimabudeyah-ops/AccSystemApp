"""Operations service: vendor returns, tax filing, recurring runner, bank reconcile."""
from __future__ import annotations
import hashlib
import logging
import secrets
import uuid
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import text as _text
from ..extensions import db
from ..models.ops import (
    VendorReturn, VendorReturnLine, TaxReturn, RecurringEntry,
)
from ..models.product import Product, StockMove, StockQuant
from . import posting_service, sequence_service
from .errors import NotFoundError, BadStateError, ValidationError, AccountingError

log = logging.getLogger(__name__)


def _account(entity_id, code: str):
    from ..models.account import Account
    acc = db.session.query(Account).filter_by(entity_id=entity_id, code=code, is_deleted=False).first()
    if acc is None:
        raise NotFoundError(f"Account {code} not configured")
    return acc


# ------------------------------------------------------------- vendor returns

def create_vendor_return(*, tenant_id, entity_id, supplier_id, bill_id=None,
                         return_date=None, reason, warehouse_id=None, lines, actor_id):
    tenant_id = uuid.UUID(str(tenant_id))
    number = sequence_service.next_doc_number(tenant_id=tenant_id,
                                              entity_id=uuid.UUID(str(entity_id)),
                                              doctype="vendor_return", year=(return_date or date.today()).year)
    total = sum(Decimal(str(l["returned_qty"])) * Decimal(str(l["unit_price"])) for l in lines)
    ret = VendorReturn(tenant_id=tenant_id, entity_id=uuid.UUID(str(entity_id)),
                       doc_number=number, supplier_id=uuid.UUID(str(supplier_id)),
                       bill_id=uuid.UUID(str(bill_id)) if bill_id else None,
                       return_date=return_date or date.today(), reason=reason,
                       warehouse_id=uuid.UUID(str(warehouse_id)) if warehouse_id else None,
                       total_amount=total, status="draft",
                       created_by=actor_id, updated_by=actor_id)
    db.session.add(ret)
    db.session.flush()
    for i, l in enumerate(lines, 1):
        db.session.add(VendorReturnLine(
            tenant_id=tenant_id, return_id=ret.id, line_number=i,
            product_id=uuid.UUID(str(l["product_id"])), returned_qty=l["returned_qty"],
            unit_price=l["unit_price"],
            line_total=Decimal(str(l["returned_qty"])) * Decimal(str(l["unit_price"])),
            location_id=uuid.UUID(str(l["location_id"])) if l.get("location_id") else None,
            created_by=actor_id, updated_by=actor_id))
    db.session.commit()
    return ret


def post_vendor_return(return_id: uuid.UUID, *, actor_id, stock_account_code="1310"):
    """ترحيل مرتجع مورد: مورد مدين / مخزون دائن + صرف مخزني."""
    ret = db.session.get(VendorReturn, return_id)
    if ret is None or ret.is_deleted:
        raise NotFoundError("Return not found")
    if ret.status == "posted":
        return ret
    if ret.status != "draft":
        raise BadStateError(f"Cannot post from {ret.status}")
    from ..models.journal import Journal
    journal = db.session.query(Journal).filter_by(
        tenant_id=ret.tenant_id, entity_id=ret.entity_id, code="PURCH", is_deleted=False).first()
    if journal is None:
        raise NotFoundError("Journal PURCH not configured")
    stock_acc = _account(ret.entity_id, stock_account_code)
    supplier_acc = _account(ret.entity_id, "2010")
    if ret.warehouse_id:
        missing = [l.line_number for l in ret.lines
                   if not l.is_deleted and l.location_id is None]
        if missing:
            raise ValidationError(f"Return lines need locations: {missing[:10]}")
    # ضريبة المدخلات المعكوسة: نسبة من الفاتورة الأصلية المرتبطة (إن وجدت)
    vat_ratio = Decimal("0")
    if ret.bill_id:
        from ..models.purchases import VendorBill as _Bill
        bill = db.session.get(_Bill, ret.bill_id)
        if bill is not None and not bill.is_deleted and float(bill.grand_total or 0) > 0:
            vat_ratio = Decimal(str(bill.tax_total or 0)) / Decimal(str(bill.grand_total))
    vat_part = (Decimal(str(ret.total_amount)) * vat_ratio).quantize(Decimal("0.001"))
    net_part = Decimal(str(ret.total_amount)) - vat_part
    try:
        input_vat = _account(ret.entity_id, "2141")
    except NotFoundError:
        input_vat = None
    if input_vat is None or vat_part <= 0:
        vat_part = Decimal("0")
        net_part = Decimal(str(ret.total_amount))
    for l in ret.lines:
        if l.is_deleted or l.location_id is None:
            continue
        product = db.session.get(Product, l.product_id)
        db.session.add(StockMove(
            tenant_id=ret.tenant_id, entity_id=ret.entity_id, product_id=l.product_id,
            uom_id=product.base_uom_id, qty=float(l.returned_qty),
            source_location_id=l.location_id, move_type="return", status="done",
            reference=ret.doc_number, move_date=ret.return_date,
            unit_cost=float(product.avg_cost or 0),
            created_by=actor_id, updated_by=actor_id))
        db.session.flush()
        q = db.session.query(StockQuant).filter_by(product_id=l.product_id, location_id=l.location_id).first()
        if q is None or float(q.qty) - float(q.reserved_qty) < float(l.returned_qty) - 0.001:
            raise ValidationError("Insufficient stock for vendor return")
        q.qty = float(q.qty) - float(l.returned_qty)
    # حساب متوسط التكلفة الإجمالي للمرتجع (مطابق للـ StockMove)
    avg_cost_total = Decimal("0")
    for l in ret.lines:
        if l.is_deleted:
            continue
        product = db.session.get(Product, l.product_id)
        avg_cost_total += Decimal(str(l.returned_qty)) * Decimal(str(product.avg_cost or 0))
    avg_cost_total = avg_cost_total.quantize(Decimal("0.001"))
    # فرق التكلفة: الفرق بين صافي الفاتورة ومتوسط التكلفة يذهب لتسوية المخزون
    cost_diff = (net_part - avg_cost_total).quantize(Decimal("0.001"))
    gl_lines = [{"account_id": supplier_acc.id, "debit": float(ret.total_amount), "credit": 0,
                 "partner_id": ret.supplier_id},
                {"account_id": stock_acc.id, "debit": 0, "credit": float(avg_cost_total),
                 "partner_id": ret.supplier_id}]
    if vat_part > 0:
        gl_lines.append({"account_id": input_vat.id, "debit": 0, "credit": float(vat_part),
                         "partner_id": ret.supplier_id})
    if abs(cost_diff) >= Decimal("0.001"):
        adj_acc = _account(ret.entity_id, "5590")
        if cost_diff > 0:
            # صافي الفاتورة > متوسط التكلفة → ربح على المردود (دائن)
            gl_lines.append({"account_id": adj_acc.id, "debit": 0, "credit": float(cost_diff)})
        else:
            # صافي الفاتورة < متوسط التكلفة → خسارة على المردود (مدين)
            gl_lines.append({"account_id": adj_acc.id, "debit": float(-cost_diff), "credit": 0})
    entry = posting_service.create_entry(
        {"tenant_id": ret.tenant_id, "entity_id": ret.entity_id, "journal_id": journal.id,
         "entry_type": "source", "document_date": ret.return_date, "posting_date": ret.return_date,
         "description": f"مرتجع مورد {ret.doc_number}", "source_module": "purchases",
         "source_document_id": ret.id, "source_event_key": f"purchases.vreturn.{ret.id}.v1"},
        gl_lines,
        actor_id=actor_id)
    entry = posting_service.post_entry(entry.id, actor_id)
    ret.journal_entry_id = entry.id
    ret.vat_amount = float(vat_part)
    ret.status = "posted"
    db.session.commit()
    return ret


# ------------------------------------------------------------- tax filing

def file_tax_return(*, tenant_id, entity_id, tax_id, period_code, actor_id):
    """احتساب الإقرار: مخرجات (فواتير − إشعارات دائنة) − مدخلات (فواتير موردين − مرتجعات).

    يُقيّد بالكيان والشهر المحاسبي (تاريخ المستند). tax_due تُحفظ للتوافق = المخرجات،
    وصافي المستحق في net_due = المخرجات − المدخلات.
    """
    from ..models.treasury import Tax
    tax = db.session.get(Tax, uuid.UUID(str(tax_id)))
    if tax is None:
        raise NotFoundError("Tax not found")
    existing = db.session.query(TaxReturn).filter_by(
        tenant_id=uuid.UUID(str(tenant_id)), entity_id=uuid.UUID(str(entity_id)),
        tax_id=tax.id, period_code=period_code, is_deleted=False).first()
    if existing:
        return existing
    year, month = period_code.split("-")
    params = {"t": str(tenant_id), "e": str(entity_id),
              "x": str(tax_id), "y": int(year), "m": int(month)}
    month_cond_inv = ("date_trunc('month', i.invoice_date)::date = "
                      "make_date(CAST(:y AS INTEGER), CAST(:m AS INTEGER), 1)")
    out = db.session.execute(_text(
        "SELECT COALESCE(SUM(t.tax_amount),0)::float, COALESCE(SUM(i.grand_total),0)::float "
        "FROM customer_invoice_taxes t JOIN customer_invoices i ON i.id = t.invoice_id "
        "WHERE t.tenant_id = :t AND i.entity_id = :e AND t.tax_id = :x AND i.status = 'posted' "
        f"AND {month_cond_inv} AND t.is_deleted = FALSE"),
        params).first()
    cn = db.session.execute(_text(
        "SELECT COALESCE(SUM(n.tax_total),0)::float "
        "FROM credit_notes n JOIN credit_note_lines l ON l.note_id = n.id "
        "WHERE n.tenant_id = :t AND n.entity_id = :e AND n.status = 'posted' "
        "AND date_trunc('month', n.note_date)::date = make_date(CAST(:y AS INTEGER), CAST(:m AS INTEGER), 1) "
        "AND n.is_deleted = FALSE AND l.is_deleted = FALSE AND l.tax_id = :x"),
        params).first()
    bills = db.session.execute(_text(
        "SELECT COALESCE(SUM(b.tax_total),0)::float, COALESCE(SUM(b.grand_total),0)::float "
        "FROM vendor_bills b WHERE b.tenant_id = :t AND b.entity_id = :e AND b.status = 'posted' "
        "AND date_trunc('month', b.bill_date)::date = make_date(CAST(:y AS INTEGER), CAST(:m AS INTEGER), 1) "
        "AND b.is_deleted = FALSE"),
        params).first()
    vret = db.session.execute(_text(
        "SELECT COALESCE(SUM(r.vat_amount),0)::float "
        "FROM vendor_returns r WHERE r.tenant_id = :t AND r.entity_id = :e AND r.status = 'posted' "
        "AND date_trunc('month', r.return_date)::date = make_date(CAST(:y AS INTEGER), CAST(:m AS INTEGER), 1) "
        "AND r.is_deleted = FALSE"),
        params).first()
    output_tax = round((out[0] or 0.0) - (cn[0] or 0.0), 3)
    input_tax = round((bills[0] or 0.0) - (vret[0] or 0.0), 3)
    ret = TaxReturn(tenant_id=uuid.UUID(str(tenant_id)), entity_id=uuid.UUID(str(entity_id)),
                    tax_id=tax.id, period_code=period_code,
                    sales_total=(out[1] or 0.0), tax_due=output_tax,
                    purchase_total=(bills[1] or 0.0), input_tax=input_tax,
                    output_tax=output_tax, net_due=round(output_tax - input_tax, 3),
                    status="filed", created_by=actor_id, updated_by=actor_id)
    from datetime import datetime
    ret.filed_at = datetime.utcnow()
    ret.filed_by = actor_id
    db.session.add(ret)
    db.session.commit()
    return ret


# ------------------------------------------------------------- recurring

def run_due_recurring(*, tenant_id=None, actor_id, today=None):
    """تشغيل القيود المتكررة المستحقة (شهري/ربع/سنوي) — idempotent بالتاريخ."""
    from dateutil.relativedelta import relativedelta
    today = today or date.today()
    q = db.session.query(RecurringEntry).filter_by(is_deleted=False, is_active=True)
    if tenant_id:
        q = q.filter_by(tenant_id=uuid.UUID(str(tenant_id)))
    ran = []
    for r in q.filter(RecurringEntry.next_run_on <= today).all():
        key = f"recurring.{r.id}.{r.next_run_on.isoformat()}.v1"
        from . import event_service
        if event_service.get_by_key(tenant_id=r.tenant_id, entity_id=r.entity_id, event_key=key):
            _advance(r)
            continue
        lines = [{"account_id": uuid.UUID(str(x["account_id"])),
                  "debit": x.get("debit", 0), "credit": x.get("credit", 0)}
                 for x in (r.template.get("lines", []))]
        entry = posting_service.create_entry(
            {"tenant_id": r.tenant_id, "entity_id": r.entity_id, "journal_id": r.journal_id,
             "entry_type": "accrual", "document_date": r.next_run_on, "posting_date": r.next_run_on,
             "description": f"{r.description} ({r.next_run_on})", "source_module": "recurring",
             "source_document_id": r.id, "source_event_key": key},
            lines, actor_id=actor_id)
        entry = posting_service.post_entry(entry.id, actor_id)
        _advance(r)
        ran.append(str(entry.id))
    db.session.commit()
    return ran


def _advance(r):
    from dateutil.relativedelta import relativedelta
    step = {"monthly": relativedelta(months=1), "quarterly": relativedelta(months=3),
            "yearly": relativedelta(years=1)}[r.frequency]
    r.last_run_on = r.next_run_on
    r.next_run_on = r.next_run_on + step


# ------------------------------------------------------------- bank reconcile

def reconcile_statement(statement_id: uuid.UUID, *, actor_id, tolerance_days: int = 3):
    """مطابقة آلية: مبلغ متساوٍ وتاريخ ± أيام مع قيود مرحلة غير مطابقة."""
    from ..models.ops import BankStatement, BankStatementLine
    from ..models.journal import JournalEntry, JournalLine
    st = db.session.get(BankStatement, statement_id)
    if st is None or st.is_deleted:
        raise NotFoundError("Statement not found")
    matched = 0
    for line in st.lines:
        if line.is_deleted or line.is_matched:
            continue
        cand = (db.session.query(JournalLine, JournalEntry)
                .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
                .filter(JournalEntry.tenant_id == st.tenant_id,
                        JournalEntry.status == "posted",
                        JournalEntry.is_reversed.is_(False),
                        JournalLine.is_deleted.is_(False))
                .filter((JournalLine.debit == abs(float(line.amount))) |
                        (JournalLine.credit == abs(float(line.amount))))
                .filter(JournalEntry.posting_date.between(
                    line.txn_date - timedelta(days=tolerance_days),
                    line.txn_date + timedelta(days=tolerance_days)))
                .first())
        if cand:
            jl, je = cand
            line.is_matched = True
            line.matched_entry_id = je.id
            matched += 1
    db.session.commit()
    return {"statement_id": str(st.id), "matched": matched}


# ------------------------------------------------------------- password reset

def request_password_reset(*, tenant_id, username):
    """إصدار توكن استعادة (يُسجل في السجل بلا SMTP في التطوير)."""
    from ..models.user import User
    from ..models.tenant import Tenant
    from ..models.ops import PasswordResetToken
    from datetime import datetime, timedelta
    from sqlalchemy import text as _text
    try:
        tid = uuid.UUID(str(tenant_id))
    except (ValueError, AttributeError):
        t = db.session.query(Tenant).filter_by(code=str(tenant_id).strip(), is_deleted=False).first()
        if t is None:
            return {"sent": True}
        tid = t.id
    db.session.execute(_text('SET LOCAL "app.current_tenant_id" = :t'), {"t": str(tid)})
    user = db.session.query(User).filter(
        User.tenant_id == tid,
        ((User.username == username) | (User.email == username)),
        User.is_deleted.is_(False)).first()
    if user is None:
        return {"sent": True}  # لا تكشف وجود الحساب
    raw = secrets.token_urlsafe(32)
    db.session.add(PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(hours=2)))
    db.session.commit()
    log.warning("password reset token for %s: %s (dev only — wire SMTP in prod)", username, raw)
    return {"sent": True}


def reset_password(*, token: str, new_password: str):
    from ..models.user import User
    from ..models.ops import PasswordResetToken
    from ..utils.security import validate_password, hash_password
    from datetime import datetime
    validate_password(new_password)
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.session.query(PasswordResetToken).filter_by(token_hash=digest).first()
    if row is None or row.used_at or row.expires_at < datetime.utcnow():
        raise ValidationError("Invalid or expired token")
    user = db.session.get(User, row.user_id)
    user.password_hash = hash_password(new_password)
    row.used_at = datetime.utcnow()
    db.session.commit()
    return {"reset": True}
