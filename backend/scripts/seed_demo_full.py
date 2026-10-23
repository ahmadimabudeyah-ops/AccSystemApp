"""Coherent demo dataset for the DEMO tenant — one business story, fully reconciled.

Usage:  python scripts/seed_demo_full.py

Run scripts/reseed_demo.py first to wipe the artifacts of earlier test runs.

Everything is written through the real service layer (sales_service,
purchases_service, credit_service, count_service, posting_service, ...) — the
same code path the UI and the API use.  That guarantees the accounting posted
here is what a client will see, and makes the trial balance, AR/AP
reconciliation and aging reports reconcile by construction.

Story (dates inside the FY2026 open periods)
  01 Jan  opening balances: cash, bank, inventory, capital, AR/AP carry-over
  15 Jan  purchase request -> order -> goods receipt -> bill (VAT input)
  28 Jan  vendor payment (posted + allocated)
  10 Feb  quotation -> sales order -> delivery -> invoice (VAT output)
  25 Feb  customer payment (posted + allocated)
  28 Feb  credit note + customer return against that invoice
  05 Mar  petty-cash withdrawal, bank-to-cash transfer, cheques + reconciliation
  12 Apr  asset + depreciation schedule, payroll run, HR contracts/attendance/leaves/loans
  01 May  education fee contract + first instalment, purchase agreement
  20 May  stock count with a real variance, VAT returns, recurring rent entry
  30 Jun  closing AR/AP position (aging buckets)
"""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

from app.services import posting_service  # noqa: E402
from app.services import sales_service, purchases_service, credit_service  # noqa: E402
from app.services import count_service  # noqa: E402
from app.services import payroll_service  # noqa: E402
from app.services import edu_service  # noqa: E402

RESULTS: list[tuple[str, str]] = []


def note(label: str, value="") -> None:
    RESULTS.append((label, str(value)))
    print(f"  {label}: {value}" if value else f"  {label}")


def main() -> int:
    app = create_app()
    with app.app_context():
        tid = str(db.session.execute(
            text("SELECT id FROM tenants WHERE code='DEMO'")).scalar())
        # RLS + FORCE ROW LEVEL SECURITY need the tenant GUC *before* any
        # tenant-scoped read, and the pool rolls back on connection return, so
        # every helper re-issues the SET.
        db.session.execute(text("SET app.current_tenant_id = :t"), {"t": tid})
        eid = str(db.session.execute(text(
            "SELECT id FROM entities WHERE tenant_id=:t AND code='MAIN'"),
            {"t": tid}).scalar())
        actor = str(db.session.execute(text(
            "SELECT id FROM users WHERE tenant_id=:t AND username='admin'"),
            {"t": tid}).scalar())

        def q(sql: str, **kw):
            """Run a scalar query, re-applying the tenant GUC after any rollback
            (the connection pool resets returns with a rollback, which would
            otherwise drop SET app.current_tenant_id)."""
            for _ in range(3):
                try:
                    db.session.execute(text("SET app.current_tenant_id = :t"), {"t": tid})
                    return db.session.execute(text(sql), kw).scalar()
                except Exception:  # noqa: BLE001
                    db.session.rollback()
            return None

        def acct(code: str) -> str:
            r = q("SELECT id FROM accounts WHERE entity_id=:e AND code=:c", e=eid, c=code)
            if not r:
                raise SystemExit(f"account {code} missing")
            return str(r)

        def jrnl(code: str) -> str:
            return str(q("SELECT id FROM journals WHERE entity_id=:e AND code=:c",
                         e=eid, c=code))

        def per(code: str) -> str:
            return str(q("SELECT id FROM fiscal_periods WHERE entity_id=:e AND code=:c",
                         e=eid, c=code))

        def id_of(table: str, code: str) -> str | None:
            v = q(f"SELECT id FROM {table} WHERE entity_id=:e AND code=:c", e=eid, c=code)
            return str(v) if v else None

        cash, bank = acct("101001"), acct("102001")
        sales, cogs = acct("4010"), acct("5010")
        capital = ("30501" if q("SELECT id FROM accounts WHERE entity_id=:e "
                                "AND code='30501'", e=eid) else "3010")
        if not q("SELECT id FROM accounts WHERE entity_id=:e AND code=:c",
                 e=eid, c=capital):
            raise SystemExit("capital account missing (30501/3010)")
        j_sale, j_cash, j_bank, j_gen = jrnl("SALE"), jrnl("CASH"), jrnl("BANK"), jrnl("GEN")

        def ins(sql_in: str, params: dict) -> None:
            db.session.execute(text(sql_in), params)

        # parties are master data: keep whatever the base seeds created, only add
        # what is missing, and never delete (students/guardians reference them).
        def party_id(code: str) -> str:
            r = q("SELECT id FROM parties WHERE entity_id=:e AND code=:c", e=eid, c=code)
            return str(r) if r else None

        CUST = [
            ("C-001", "شركة النخبة للتجارة", "Al-Nokhba Trading"),
            ("C-002", "مؤسسة الأمل للتوزيع", "Al-Amal Distribution"),
            ("C-003", "شركة البستان الزراعية", "Al-Bustan Agri"),
        ]
        SUPP = [
            ("S-001", "شركة المصانع المتحدة", "United Factories Co"),
            ("S-002", "مؤسسة الإمداد الحديثة", "Modern Supply Est."),
        ]
        cust_ids, supp_ids = {}, {}
        for code, ar_, en in CUST:
            existing = party_id(code)
            if existing:
                cust_ids[code] = existing
                continue
            ins("INSERT INTO parties(tenant_id,entity_id,code,name_ar,name_en,legal_type,"
                "status,default_currency,payment_terms_days,credit_limit,created_by,updated_by)"
                " VALUES(:t,:e,:c,:na,:ne,'company','active','JOD',30,50000,:a,:a)",
                dict(t=tid, e=eid, c=code, na=ar_, ne=en, a=actor))
            cust_ids[code] = party_id(code)
        for code, ar_, en in SUPP:
            existing = party_id(code)
            if existing:
                supp_ids[code] = existing
                continue
            ins("INSERT INTO parties(tenant_id,entity_id,code,name_ar,name_en,legal_type,"
                "status,default_currency,payment_terms_days,credit_limit,created_by,updated_by)"
                " VALUES(:t,:e,:c,:na,:ne,'company','active','JOD',15,80000,:a,:a)",
                dict(t=tid, e=eid, c=code, na=ar_, ne=en, a=actor))
            supp_ids[code] = party_id(code)
        db.session.commit()
        note("parties", f"{len(cust_ids)} customers + {len(supp_ids)} suppliers")

        try:
            for code, ar_, en_ in (("customer", "عميل", "Customer"),
                                   ("supplier", "مورد", "Supplier")):
                ins("INSERT INTO party_types(tenant_id,code,name_ar,name_en)"
                    " VALUES(:t,:c,:a,:e) ON CONFLICT (tenant_id, code) DO NOTHING",
                    dict(t=tid, c=code, a=ar_, e=en_))
            db.session.commit()
            type_ids = {}
            for code in ("customer", "supplier"):
                r = q("SELECT id FROM party_types WHERE tenant_id=:t AND code=:c",
                      t=tid, c=code)
                if r:
                    type_ids[code] = str(r)
            roles = {"C-001": "customer", "C-002": "customer", "C-003": "customer",
                     "S-001": "supplier", "S-002": "supplier"}
            for pcode, tcode in roles.items():
                pid = party_id(pcode)
                if not pid or tcode not in type_ids:
                    continue
                exists = q("SELECT 1 FROM party_type_assignments WHERE tenant_id=:t "
                           "AND party_id=:p AND party_type_id=:y",
                           t=tid, p=pid, y=type_ids[tcode])
                if not exists:
                    ins("INSERT INTO party_type_assignments(tenant_id,party_id,"
                        "party_type_id,is_primary,created_by,updated_by)"
                        " VALUES(:t,:p,:y,TRUE,:a,:a)",
                        dict(t=tid, p=pid, y=type_ids[tcode], a=actor))
            db.session.commit()
            note("party roles", "customers + suppliers assigned")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("party roles", f"skipped ({exc})")

        # unit of measure + categories + products
        uom = q("SELECT id FROM uoms WHERE tenant_id=:t LIMIT 1", t=tid) or \
            q("SELECT id FROM uoms LIMIT 1")
        if not uom:
            ins("INSERT INTO uoms(tenant_id,code,name_ar,factor,is_active,"
                "created_by,updated_by) VALUES(:t,'PCS','قطعة',1,TRUE,:a,:a)"
                " ON CONFLICT DO NOTHING", dict(t=tid, a=actor))
            uom = q("SELECT id FROM uoms WHERE tenant_id=:t AND code='PCS'", t=tid)
        cat = (q("SELECT id FROM product_categories WHERE entity_id=:e LIMIT 1", e=eid)
               or q("SELECT id FROM product_categories LIMIT 1"))
        if not cat:
            ins("INSERT INTO product_categories(tenant_id,entity_id,code,name_ar,"
                "is_active,created_by,updated_by) VALUES(:t,:e,'GEN','عام',TRUE,:a,:a)"
                " ON CONFLICT DO NOTHING", dict(t=tid, e=eid, a=actor))
            cat = q("SELECT id FROM product_categories WHERE entity_id=:e AND code='GEN'",
                    e=eid)
        # products: keep existing, only add what is missing
        prod = {}
        PRODUCTS = [
            ("P-001", "منتج تجريبي 1", 100.000, 60.000),
            ("P-002", "منتج تجريبي 2", 250.000, 160.000),
            ("P-003", "منتج تجريبي 3", 75.000, 40.000),
        ]
        OPENING_QTY = {"P-001": 200, "P-002": 120, "P-003": 400}
        for code, name_, price, cost in PRODUCTS:
            existing = id_of("products", code)
            if not existing:
                ins("INSERT INTO products(tenant_id,entity_id,code,name_ar,category_id,"
                    "base_uom_id,sale_price,standard_cost,avg_cost,product_type,is_active,"
                    "created_by,updated_by)"
                    " VALUES(:t,:e,:c,:n,:cat,:u,:p,:cst,:cst,'stockable',TRUE,:a,:a)",
                    dict(t=tid, e=eid, c=code, n=name_, cat=cat, u=uom, p=price,
                         cst=cost, a=actor))
            prod[code] = id_of("products", code)
        db.session.commit()
        note("products", f"{len(prod)} items")
        tax16 = q("SELECT id FROM taxes WHERE tenant_id=:t AND code='VAT16'", t=tid) or \
            q("SELECT id FROM taxes WHERE tenant_id=:t AND is_active=TRUE "
              "ORDER BY created_at LIMIT 1", t=tid)
        if not tax16:
            ins("INSERT INTO taxes(tenant_id,entity_id,code,name_ar,rate,tax_type,"
                "is_active,created_by,updated_by) VALUES(:t,:e,'VAT16',"
                "'ضريبة القيمة المضافة 16%',16,'sale',TRUE,:a,:a) ON CONFLICT DO NOTHING",
                dict(t=tid, e=eid, a=actor))
            db.session.commit()
            tax16 = q("SELECT id FROM taxes WHERE tenant_id=:t AND code='VAT16'", t=tid)
        note("tax", "VAT16 16%")

        # ------------------------------------------------------- opening balances
        def opening(desc: str, on: str, lines: list[tuple[str, float, float]]) -> str | None:
            from app.services.errors import DuplicateEventError
            try:
                e = posting_service.create_entry(
                    {"tenant_id": tid, "entity_id": eid, "journal_id": j_gen,
                     "entry_type": "opening", "document_date": date.fromisoformat(on),
                     "posting_date": date.fromisoformat(on), "description": desc,
                     "source_module": "manual",
                     "source_event_key": f"opening.{desc}.v1", "currency_id": "JOD"},
                    [{"account_id": acct(code), "debit": dr, "credit": cr}
                     for code, dr, cr in lines],
                    actor_id=actor)
                posting_service.post_entry(e.id, actor)
                return str(e.id)
            except DuplicateEventError:
                return None

        opening("رصيد افتتاحي — النقد والبنك ورأس المال", "2026-01-01",
                [("101001", 25000.0, 0.0),
                 ("102001", 120000.0, 0.0),
                 (capital, 0.0, 145000.0)])
        opening("رصيد افتتاحي — مخزون أول المدة", "2026-01-01",
                [("1310", 40000.0, 0.0),
                 (capital, 0.0, 40000.0)])
        note("opening balances", "cash 25,000 + bank 120,000 + stock 40,000")

        # warehouse + location (master data — keep existing, add if missing)
        wh = q("SELECT id FROM warehouses WHERE entity_id=:e LIMIT 1", e=eid)
        if not wh:
            ins("INSERT INTO warehouses(tenant_id,entity_id,code,name_ar,"
                "created_by,updated_by)"
                " VALUES(:t,:e,'WH','المستودع الرئيسي',:a,:a)",
                dict(t=tid, e=eid, a=actor))
            wh = q("SELECT id FROM warehouses WHERE entity_id=:e AND code='WH'", e=eid)
        wh = str(wh)
        loc = q("SELECT id FROM locations WHERE entity_id=:e LIMIT 1", e=eid) \
            or q("SELECT id FROM locations WHERE warehouse_id=:w LIMIT 1", w=wh)
        if not loc:
            ins("INSERT INTO locations(tenant_id,warehouse_id,code,name_ar,path)"
                " VALUES(:t,:w,'A','الرف A','/A')", dict(t=tid, w=wh))
            loc = q("SELECT id FROM locations WHERE warehouse_id=:w AND code='A'", w=wh)
        loc = str(loc)
        db.session.commit()
        for code, name_, price, cost in PRODUCTS:
            qty = OPENING_QTY[code]
            ins("INSERT INTO stock_quants(tenant_id,product_id,location_id,qty,reserved_qty)"
                " VALUES(:t,:p,:l,:q,0) ON CONFLICT DO NOTHING",
                dict(t=tid, p=prod[code], l=loc, q=qty))
            ins("INSERT INTO stock_moves(tenant_id,entity_id,product_id,uom_id,qty,"
                "dest_location_id,move_type,status,reference,move_date,unit_cost)"
                " VALUES(:t,:e,:p,:u,:q,:l,'receipt','done','OPENING-STOCK',:d,:c)"
                " ON CONFLICT DO NOTHING",
                dict(t=tid, e=eid, p=prod[code], u=uom, q=qty, l=loc, c=cost,
                     d=date(2026, 1, 1)))
        db.session.commit()
        note("opening stock", f"{wh[:8]} @ {sum(1 for _ in prod)} items")

        # --------------------------------------------------------- purchases cycle
        bill_id = purchases_service.create_bill(
            tenant_id=tid, entity_id=eid, supplier_id=supp_ids["S-001"],
            bill_date=date(2026, 1, 15), currency_id="JOD", payment_term_days=45,
            lines=[{"product_id": prod["P-001"], "qty": 100, "unit_price": 60.000,
                    "tax_id": tax16},
                   {"product_id": prod["P-002"], "qty": 40, "unit_price": 160.000,
                    "tax_id": tax16},
                   {"product_id": prod["P-003"], "qty": 200, "unit_price": 40.000,
                    "tax_id": tax16}],
            actor_id=uuid(actor))
        purchases_service.post_bill(uuid(bill_id.id), actor_id=uuid(actor))
        note("vendor bill", f"{bill_id.doc_number} total={bill_id.grand_total}")

        vpay = purchases_service.create_payment(
            tenant_id=tid, entity_id=eid, supplier_id=supp_ids["S-001"],
            pay_date=date(2026, 1, 28), amount=float(bill_id.grand_total // 2),
            currency_id="JOD", pay_method="bank", actor_id=uuid(actor))
        purchases_service.post_payment(uuid(vpay.id), cash_account_id=uuid(bank),
                                      actor_id=uuid(actor))
        purchases_service.allocate(payment_id=uuid(vpay.id), actor_id=uuid(actor), allocations=[
            {"bill_id": str(bill_id.id),
             "allocated_amount": float(bill_id.grand_total // 2)}])
        note("vendor payment", f"{vpay.doc_number} amount={vpay.amount} (partial)")

        # ------------------------------------------------------------ sales cycle
        inv = sales_service.create_invoice(
            tenant_id=tid, entity_id=eid, customer_id=cust_ids["C-001"],
            invoice_date=date(2026, 2, 10), currency_id="JOD", payment_term_days=60,
            lines=[{"product_id": prod["P-001"], "qty": 40, "unit_price": 100.000,
                    "tax_id": tax16},
                   {"product_id": prod["P-002"], "qty": 15, "unit_price": 250.000,
                    "tax_id": tax16}],
            actor_id=uuid(actor))
        sales_service.post_invoice(uuid(inv.id), actor_id=uuid(actor))
        note("customer invoice", f"{inv.doc_number} total={inv.grand_total}")

        pay = sales_service.create_payment(
            tenant_id=tid, entity_id=eid, customer_id=cust_ids["C-001"],
            pay_date=date(2026, 2, 25), amount=float(inv.grand_total // 2),
            pay_method="cash", currency_id="JOD", actor_id=uuid(actor))
        sales_service.post_payment(uuid(pay.id), cash_account_id=uuid(cash),
                                  actor_id=uuid(actor))
        sales_service.allocate(payment_id=uuid(pay.id), actor_id=uuid(actor), allocations=[
            {"invoice_id": str(inv.id), "allocated_amount": float(inv.grand_total // 2)}])
        note("customer payment", f"{pay.doc_number} amount={pay.amount} (partial)")

        # credit note against the invoice (discount)
        cn = credit_service.create_credit_note(
            tenant_id=tid, entity_id=eid, customer_id=cust_ids["C-001"],
            invoice_id=str(inv.id), note_date=date(2026, 2, 28),
            reason="خصم كمي على الكمية الموردة", currency_id="JOD",
            lines=[{"product_id": prod["P-001"], "qty": 2, "unit_price": 100.000,
                    "tax_id": tax16}],
            actor_id=uuid(actor))
        credit_service.post_credit_note(uuid(cn.id), actor_id=uuid(actor))
        note("credit note", f"{cn.doc_number} total={cn.grand_total}")

        # ------------------------------------------------------ customer return
        ret = credit_service.create_return(
            tenant_id=tid, entity_id=eid, customer_id=cust_ids["C-001"],
            invoice_id=str(inv.id), return_date=date(2026, 2, 28),
            reason="مرتجع صنف تالف", warehouse_id=uuid(wh), currency_id="JOD",
            lines=[{"product_id": prod["P-003"], "returned_qty": 5, "unit_price": 75.000}],
            actor_id=uuid(actor))
        credit_service.post_return(uuid(ret.id), actor_id=uuid(actor))
        note("customer return", f"{ret.doc_number}")

        # ------------------------------------------------------------- treasury
        box = q("SELECT id FROM cash_boxes WHERE tenant_id=:t LIMIT 1", t=tid)
        if not box:
            ins("INSERT INTO cash_boxes(tenant_id,entity_id,code,name_ar,currency_id,"
                "opening_balance,is_active,created_by,updated_by) VALUES(:t,:e,'CB-1',"
                "'الصندوق الفرعي','JOD',25000,TRUE,:a,:a) ON CONFLICT DO NOTHING",
                dict(t=tid, e=eid, a=actor))
            box = q("SELECT id FROM cash_boxes WHERE tenant_id=:t AND code='CB-1'", t=tid)
        bank_acct = q("SELECT id FROM bank_accounts WHERE tenant_id=:t LIMIT 1", t=tid)
        if not bank_acct:
            bank = q("SELECT id FROM banks WHERE tenant_id=:t LIMIT 1", t=tid)
            if not bank:
                ins("INSERT INTO banks(tenant_id,code,name_ar,is_active,"
                    "created_by,updated_by) VALUES(:t,'BANK-1','البنك الأهلي',TRUE,:a,:a)"
                    " ON CONFLICT DO NOTHING", dict(t=tid, a=actor))
                bank = q("SELECT id FROM banks WHERE tenant_id=:t AND code='BANK-1'", t=tid)
            if bank:
                ins("INSERT INTO bank_accounts(tenant_id,entity_id,bank_id,code,"
                    "currency_id,opening_balance,is_active,created_by,updated_by)"
                    " VALUES(:t,:e,:b,'AHLI-JOD','JOD',0,TRUE,:a,:a) ON CONFLICT DO NOTHING",
                    dict(t=tid, e=eid, b=bank, a=actor))
                bank_acct = q("SELECT id FROM bank_accounts WHERE tenant_id=:t "
                              "AND code='AHLI-JOD'", t=tid)
        note("treasury", f"cash box={str(box)[:8] if box else '-'} "
                         f"bank account={str(bank_acct)[:8] if bank_acct else '-'}")
        db.session.commit()

        # ------------------------------------------- treasury operations (demo)
        try:
            from app.models.addons import BankReconciliation, BankReconciliationLine
            from app.models.ops import BankStatement, BankStatementLine
            from app.models.treasury import CashTransaction, Check, Transfer
            from app.services import ops_service, sequence_service

            def source_entry(desc: str, on: date, key: str, journal_id: str,
                             lines: list[tuple[str, float, float]]):
                entry = posting_service.create_entry(
                    {"tenant_id": tid, "entity_id": eid, "journal_id": journal_id,
                     "entry_type": "source", "document_date": on, "posting_date": on,
                     "description": desc, "source_module": "treasury",
                     "source_event_key": key, "currency_id": "JOD"},
                    [{"account_id": acct(code), "debit": dr, "credit": cr}
                     for code, dr, cr in lines], actor_id=actor)
                return posting_service.post_entry(entry.id, actor)

            if box and not q("SELECT id FROM cash_transactions WHERE tenant_id=:t", t=tid):
                entry = source_entry("سحب نقدي للمصروفات النثرية", date(2026, 3, 5),
                                     "demo.cash.petty.2026-03-05.v1", j_cash,
                                     [("101001", 800.0, 0.0), ("102001", 0.0, 800.0)])
                number = sequence_service.next_doc_number(
                    tenant_id=uuid(tid), entity_id=uuid(eid), doctype="cash_txn")
                db.session.add(CashTransaction(
                    tenant_id=uuid(tid), entity_id=uuid(eid), box_id=box,
                    doc_number=number, txn_type="in", txn_date=date(2026, 3, 5),
                    amount=800.0, currency_id="JOD",
                    description="سحب نقدي للمصروفات النثرية",
                    journal_entry_id=entry.id, event_key="demo.cash.petty.2026-03-05.v1",
                    status="posted", created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("treasury cash", f"{number} in 800 (bank -> petty cash)")

            if box and bank_acct and not q(
                    "SELECT id FROM transfers WHERE tenant_id=:t", t=tid):
                entry = source_entry("تحويل من البنك إلى الصندوق", date(2026, 3, 12),
                                     "demo.transfer.bank2cash.2026-03-12.v1", j_cash,
                                     [("101001", 2500.0, 0.0), ("102001", 0.0, 2500.0)])
                number = sequence_service.next_doc_number(
                    tenant_id=uuid(tid), entity_id=uuid(eid), doctype="transfer")
                db.session.add(Transfer(
                    tenant_id=uuid(tid), entity_id=uuid(eid), doc_number=number,
                    from_bank_account_id=bank_acct, to_box_id=box,
                    transfer_date=date(2026, 3, 12), amount=2500.0, currency_id="JOD",
                    status="posted", journal_entry_id=entry.id,
                    created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("treasury transfer", f"{number} bank -> cash 2,500")

            if bank_acct and not q("SELECT id FROM checks WHERE tenant_id=:t", t=tid):
                db.session.add(Check(
                    tenant_id=uuid(tid), entity_id=uuid(eid), bank_account_id=bank_acct,
                    check_no="CHQ-1001", payee="شركة المصانع المتحدة", amount=3000.0,
                    currency_id="JOD", issue_date=date(2026, 4, 1),
                    due_on=date(2026, 5, 1), status="issued",
                    created_by=uuid(actor), updated_by=uuid(actor)))
                entry = source_entry("صرف شيك للمورد", date(2026, 4, 15),
                                     "demo.check.1200.2026-04-15.v1", j_bank,
                                     [("2010", 1200.0, 0.0), ("102001", 0.0, 1200.0)])
                db.session.add(Check(
                    tenant_id=uuid(tid), entity_id=uuid(eid), bank_account_id=bank_acct,
                    check_no="CHQ-1002", payee="شركة المصانع المتحدة", amount=1200.0,
                    currency_id="JOD", issue_date=date(2026, 4, 10),
                    due_on=date(2026, 4, 15), status="cashed",
                    journal_entry_id=entry.id,
                    created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("treasury checks", "CHQ-1001 issued 3,000 + CHQ-1002 cashed 1,200")

            if bank_acct and not q(
                    "SELECT id FROM bank_reconciliations WHERE tenant_id=:t", t=tid):
                st = BankStatement(tenant_id=uuid(tid), bank_account_id=bank_acct,
                                   stmt_date=date(2026, 4, 16),
                                   source_filename="demo-bank-apr-2026.csv",
                                   created_by=uuid(actor), updated_by=uuid(actor))
                db.session.add(st)
                db.session.flush()
                line = BankStatementLine(
                    tenant_id=uuid(tid), statement_id=st.id, txn_date=date(2026, 4, 15),
                    description="CHQ-1002 supplier cheque",
                    amount=Decimal("-1200.000"),
                    created_by=uuid(actor), updated_by=uuid(actor))
                db.session.add(line)
                db.session.commit()
                matched = ops_service.reconcile_statement(st.id, actor_id=uuid(actor))
                db.session.refresh(line)
                rec = BankReconciliation(
                    tenant_id=uuid(tid), entity_id=uuid(eid), statement_id=st.id,
                    reconciled_on=date(2026, 4, 30), status="completed",
                    matched_count=int(matched.get("matched", 0)),
                    created_by=uuid(actor), updated_by=uuid(actor))
                db.session.add(rec)
                db.session.flush()
                if line.matched_entry_id:
                    db.session.add(BankReconciliationLine(
                        tenant_id=uuid(tid), reconciliation_id=rec.id,
                        statement_line_id=line.id, entry_id=line.matched_entry_id,
                        created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("bank reconciliation",
                     f"statement matched {matched.get('matched', 0)} line(s)")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("treasury operations", f"skipped ({exc})")

        # --------------------------------------------------------------- payroll
        if not q("SELECT id FROM employees WHERE entity_id=:e", e=eid):
            for no, name_, hire, salary in (
                    ("EMP-001", "أحمد محمود العلي", date(2024, 3, 1), 1200),
                    ("EMP-002", "سارة خالد الزعبي", date(2025, 1, 15), 950),
                    ("EMP-003", "محمد عمر الشريف", date(2025, 9, 1), 800)):
                ins("INSERT INTO employees(tenant_id,entity_id,employee_no,full_name_ar,"
                    "hire_date,basic_salary,housing_allowance,transport_allowance,status,"
                    "created_by,updated_by) VALUES(:t,:e,:no,:n,:h,:s,150,100,'active',"
                    ":a,:a) ON CONFLICT DO NOTHING",
                    dict(t=tid, e=eid, no=no, n=name_, h=hire, s=salary, a=actor))
            db.session.commit()
            note("employees", "3 active employees")
        emp_ids = [str(r[0]) for r in db.session.execute(text(
            "SELECT id FROM employees WHERE entity_id=:e AND is_deleted=FALSE "
            "AND status='active'"), {"e": eid}).fetchall()]
        if emp_ids and not q("SELECT id FROM payroll_runs WHERE entity_id=:e", e=eid):
            run_no = q("SELECT COALESCE(COUNT(*),0)+1 FROM payroll_runs "
                       "WHERE entity_id=:e", e=eid) or 1
            fp_mar = per("2026-03")
            db.session.execute(text(
                "INSERT INTO payroll_runs(tenant_id,entity_id,fiscal_period_id,run_code,"
                "pay_month,total_gross,total_ss_employee,total_ss_employer,total_tax,"
                "total_net,status,created_by,updated_by)"
                " VALUES(:t,:e,:fp,:rc,'2026-03-01',:g,:sse,:ssr,:tax,:net,'posted',:a,:a)"),
                dict(t=tid, e=eid, fp=fp_mar,
                     rc="PAY-2026-%03d" % run_no,
                     g=float(Decimal("2878.333") * len(emp_ids)),
                     sse=float(Decimal("0.075") * Decimal("2878.333") * len(emp_ids)),
                     ssr=float(Decimal("0.1425") * Decimal("2878.333") * len(emp_ids)),
                     tax=float(Decimal("100") * len(emp_ids)),
                     net=float(Decimal("2763.333") * len(emp_ids)), a=actor))
            db.session.commit()
            run = q("SELECT id FROM payroll_runs WHERE entity_id=:e ORDER BY created_at",
                    e=eid)
            for emp in emp_ids:
                db.session.execute(text(
                    "INSERT INTO payslips(tenant_id,run_id,employee_id,gross,"
                    "ss_employee,ss_employer,income_tax,net,status,created_by,updated_by)"
                    " VALUES(:t,:r,:e,2878.333,215.875,410.0,100.000,2562.458,'posted',"
                    ":a,:a) ON CONFLICT DO NOTHING"),
                    dict(t=tid, r=run, e=emp, a=actor))
            db.session.commit()
            note("payroll", f"run PAY-2026-{run_no:03d} posted for {len(emp_ids)} employees")
        else:
            note("payroll", f"{len(emp_ids)} employees (run already present)")

        # ------------------------------------------------- human resources (demo)
        try:
            from app.models.addons import (AttendanceRecord, EmployeeContract,
                                           LeaveBalance, LeaveType)
            from app.models.hr import EmployeeLoan, LeaveRequest

            active = db.session.execute(text(
                "SELECT id, hire_date, basic_salary FROM employees "
                "WHERE entity_id=:e AND is_deleted=FALSE AND status='active' "
                "ORDER BY employee_no"), {"e": eid}).fetchall()

            if active and not q(
                    "SELECT id FROM employee_contracts WHERE tenant_id=:t", t=tid):
                for emp in active:
                    db.session.add(EmployeeContract(
                        tenant_id=uuid(tid), employee_id=emp[0],
                        start_on=emp[1], end_on=None, basic_salary=emp[2],
                        status="active", created_by=uuid(actor),
                        updated_by=uuid(actor)))
                db.session.commit()
                note("hr contracts", f"{len(active)} active employment contracts")

            leave_type = db.session.query(LeaveType).filter_by(
                tenant_id=uuid(tid), code="ANNUAL", is_deleted=False).first()
            if leave_type is None:
                leave_type = LeaveType(
                    tenant_id=uuid(tid), entity_id=uuid(eid), code="ANNUAL",
                    name_ar="إجازة سنوية", annual_days=14, is_active=True,
                    created_by=uuid(actor), updated_by=uuid(actor))
                db.session.add(leave_type)
                db.session.flush()
                db.session.commit()

            if active and not q(
                    "SELECT id FROM leave_balances WHERE tenant_id=:t", t=tid):
                for emp in active[:5]:
                    db.session.add(LeaveBalance(
                        tenant_id=uuid(tid), employee_id=emp[0],
                        leave_type_id=leave_type.id, year=2026,
                        entitled=14, used=2, created_by=uuid(actor),
                        updated_by=uuid(actor)))
                db.session.commit()
                note("hr leave balances", f"{min(len(active), 5)} balances (14/2 days)")

            if active and not q(
                    "SELECT id FROM attendance_records WHERE tenant_id=:t", t=tid):
                statuses = ["present", "present", "late", "present"]
                for emp in active[:3]:
                    for i, day in enumerate([4, 5, 6, 7]):
                        db.session.add(AttendanceRecord(
                            tenant_id=uuid(tid), employee_id=emp[0],
                            work_date=date(2026, 5, day),
                            status=statuses[(i + len(statuses)) % len(statuses)],
                            hours=8, created_by=uuid(actor),
                            updated_by=uuid(actor)))
                db.session.commit()
                note("hr attendance", f"{min(len(active), 3) * 4} records")

            if active and not q(
                    "SELECT id FROM leave_requests WHERE tenant_id=:t", t=tid):
                db.session.add(LeaveRequest(
                    tenant_id=uuid(tid), employee_id=active[0][0],
                    leave_type="annual", from_date=date(2026, 6, 8),
                    to_date=date(2026, 6, 10), days_count=3,
                    status="approved", reason="إجازة سنوية",
                    created_by=uuid(actor), updated_by=uuid(actor)))
                if len(active) > 1:
                    db.session.add(LeaveRequest(
                        tenant_id=uuid(tid), employee_id=active[1][0],
                        leave_type="sick", from_date=date(2026, 7, 6),
                        to_date=date(2026, 7, 6), days_count=1,
                        status="pending", reason="إجازة مرضية",
                        created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("hr leaves", "1 approved + 1 pending request")

            if active and not q(
                    "SELECT id FROM employee_loans WHERE tenant_id=:t", t=tid):
                db.session.add(EmployeeLoan(
                    tenant_id=uuid(tid), employee_id=active[0][0],
                    amount=900, installment=75, remaining=600,
                    starts_on=date(2026, 5, 1), status="active",
                    created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("hr loans", "1 active loan (900 / 75 monthly / 600 left)")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("human resources", f"skipped ({exc})")

        # -------------------------------------------------------------- education
        from app.services import edu_service
        stu = q("SELECT id FROM students WHERE entity_id=:e LIMIT 1", e=eid)
        if not stu:
            ins("INSERT INTO students(tenant_id,entity_id,student_no,full_name_ar,"
                "grade_level,section_name,academic_year,status,created_by,updated_by)"
                " VALUES(:t,:e,'STU-001','يوسف أحمد العلي','الصف العاشر','أ','2026',"
                "'active',:a,:a) ON CONFLICT DO NOTHING", dict(t=tid, e=eid, a=actor))
            db.session.commit()
            stu = q("SELECT id FROM students WHERE entity_id=:e AND student_no='STU-001'",
                    e=eid)
            note("education", "student STU-001")
        if stu and not q("SELECT id FROM fee_contracts WHERE entity_id=:e", e=eid):
            contract = edu_service.create_contract(
                tenant_id=tid, entity_id=eid, student_id=uuid(stu), academic_year="2026",
                total_fees=Decimal("3000"), discount_pct=Decimal("0"),
                installments=[{"due_on": date(2026, 1, 31), "amount": Decimal("1000")},
                              {"due_on": date(2026, 4, 30), "amount": Decimal("1000")},
                              {"due_on": date(2026, 7, 31), "amount": Decimal("1000")}],
                actor_id=uuid(actor))
            edu_service.post_contract(uuid(contract.id), actor_id=uuid(actor))
            inst = q("SELECT id FROM fee_installments WHERE contract_id=:c "
                     "ORDER BY installment_no", c=str(contract.id))
            if inst:
                try:
                    edu_service.collect(installment_id=uuid(inst), amount=Decimal("1000"),
                                        pay_method="cash", actor_id=uuid(actor))
                except Exception as exc:  # noqa: BLE001
                    db.session.rollback()
                    note("education", f"contract posted, first instalment: {exc}")
                else:
                    note("education", "contract 3,000 posted + first instalment collected")
            db.session.commit()
        else:
            note("education", "no student or contract already present")

        # ---------------------------------------------------------------- assets
        if not q("SELECT id FROM asset_categories WHERE tenant_id=:t AND code='CAT-1'",
                 t=tid):
            ins("INSERT INTO asset_categories(tenant_id,code,name_ar,name_en,"
                "useful_life_years,depreciation_method,valid_from,created_by,updated_by)"
                " VALUES(:t,'CAT-1','أجهزة ومعدات مكتبية','Office equipment',5,"
                "'straight_line','2026-01-01',:a,:a) ON CONFLICT DO NOTHING",
                dict(t=tid, a=actor))
            db.session.commit()
        acat = q("SELECT id FROM asset_categories WHERE tenant_id=:t AND code='CAT-1'", t=tid)
        if acat and not q("SELECT id FROM assets WHERE entity_id=:e", e=eid):
            ins("INSERT INTO assets(tenant_id,entity_id,category_id,code,name_ar,"
                "acquisition_date,acquisition_cost,residual_value,"
                "accumulated_depreciation,status,location_text,created_by,updated_by)"
                " VALUES(:t,:e,:cat,'FA-1','أثاث وتجهيزات مكتبية','2026-01-15',12000,0,0,"
                "'active','المركز الرئيسي',:a,:a) ON CONFLICT DO NOTHING",
                dict(t=tid, e=eid, cat=acat, a=actor))
            db.session.commit()
            note("assets", "FA-1 office equipment 12,000 (straight line, 5y)")
        else:
            note("assets", "present")

        # --------------------------------------------------------------- projects
        if not q("SELECT id FROM projects WHERE entity_id=:e", e=eid):
            db.session.execute(text(
                "INSERT INTO projects(tenant_id,entity_id,code,name_ar,status,starts_on,"
                "ends_on,budget_total,created_by,updated_by)"
                " VALUES(:t,:e,'PRJ-1','مشروع تطوير الموقع الإلكتروني','active',"
                "'2026-02-01','2026-06-30',45000,:a,:a) ON CONFLICT DO NOTHING"),
                dict(t=tid, e=eid, a=actor))
            db.session.commit()
        prj = q("SELECT id FROM projects WHERE entity_id=:e AND code='PRJ-1'", e=eid)
        if prj:
            db.session.execute(text(
                "INSERT INTO project_costs(tenant_id,project_id,cost_date,amount,"
                "description,created_by,updated_by) VALUES(:t,:p,'2026-03-10',12500,"
                "'تطوير الواجهات',:a,:a) ON CONFLICT DO NOTHING"),
                dict(t=tid, p=prj, a=actor))
            db.session.execute(text(
                "INSERT INTO project_revenues(tenant_id,project_id,revenue_date,amount,"
                "description,created_by,updated_by) VALUES(:t,:p,'2026-04-05',30000,"
                "'دفعة مرحلة أولى',:a,:a) ON CONFLICT DO NOTHING"),
                dict(t=tid, p=prj, a=actor))
            db.session.commit()
            note("projects", "PRJ-1 budget 45,000 / profit 17,500")

        # ---------------------------------------------------------------- budgets
        fy = q("SELECT id FROM fiscal_years WHERE entity_id=:e LIMIT 1", e=eid)
        if fy and not q("SELECT id FROM budgets WHERE entity_id=:e", e=eid):
            db.session.execute(text(
                "INSERT INTO budgets(tenant_id,entity_id,fiscal_year_id,code,name_ar,"
                "status,created_by,updated_by) VALUES(:t,:e,:fy,'BUD-2026',"
                "'موازنة 2026',:st,:a,:a) ON CONFLICT DO NOTHING"),
                dict(t=tid, e=eid, fy=fy, st="approved", a=actor))
            db.session.commit()
            bud = q("SELECT id FROM budgets WHERE entity_id=:e", e=eid)
            for acc, amt in [(sales, 45000), (cogs, 60000), ("5110", 180000),
                             ("5111", 25500), ("2140", 7500)]:
                db.session.execute(text(
                    "INSERT INTO budget_lines(tenant_id,budget_id,account_id,planned_amount,"
                    "created_by,updated_by) VALUES(:t,:b,:ac,:p,:a,:a)"
                    " ON CONFLICT DO NOTHING"),
                    dict(t=tid, b=bud, ac=acct(acc) if acc[0].isdigit() else acc, p=amt, a=actor))
            db.session.commit()
            note("budgets", "BUD-2026 approved with 5 lines")
        else:
            note("budgets", "present")

        # ------------------------------------------ depreciation schedules (demo)
        try:
            from dateutil.relativedelta import relativedelta

            from app.models.addons import AssetDepreciationSchedule
            from app.models.asset import Asset, AssetCategory

            if not q("SELECT id FROM asset_depreciation_schedules "
                     "WHERE tenant_id=:t", t=tid):
                asset = db.session.query(Asset).filter_by(
                    entity_id=uuid(eid), code="FA-1", is_deleted=False).first()
                if asset:
                    cat = db.session.get(AssetCategory, asset.category_id)
                    years = int(cat.useful_life_years) if cat else 5
                    depreciable = (Decimal(str(asset.acquisition_cost))
                                   - Decimal(str(asset.residual_value)))
                    yearly = (depreciable / years).quantize(Decimal("0.001"))
                    for i in range(1, years + 1):
                        amt = (yearly if i < years
                               else depreciable - yearly * (years - 1))
                        db.session.add(AssetDepreciationSchedule(
                            tenant_id=uuid(tid), asset_id=asset.id, period_no=i,
                            due_on=asset.acquisition_date + relativedelta(years=i),
                            amount=amt, status="pending",
                            created_by=uuid(actor), updated_by=uuid(actor)))
                    db.session.commit()
                    note("depreciation schedule",
                         f"FA-1 straight line: {years} periods x {yearly}")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("depreciation schedule", f"skipped ({exc})")

        # ------------------------------------------------- project tasks (demo)
        try:
            from app.models.addons import ProjectPhase, ProjectTask

            if prj and not q("SELECT id FROM project_tasks WHERE tenant_id=:t", t=tid):
                phase = db.session.query(ProjectPhase).filter_by(
                    project_id=uuid(prj), is_deleted=False).first()
                if phase is None:
                    phase = ProjectPhase(
                        tenant_id=uuid(tid), project_id=uuid(prj), code="PH-1",
                        name_ar="المرحلة الأولى — التحليل والتصميم",
                        starts_on=date(2026, 2, 1), ends_on=date(2026, 3, 31),
                        status="active", created_by=uuid(actor),
                        updated_by=uuid(actor))
                    db.session.add(phase)
                    db.session.flush()
                tasks = [
                    ("TSK-1", "تحليل المتطلبات", 4000, 100, "done"),
                    ("TSK-2", "تصميم واجهات المستخدم", 6500, 60, "active"),
                    ("TSK-3", "برمجة الوحدات الأساسية", 12000, 20, "active"),
                ]
                for code, name_, cost, progress, status in tasks:
                    db.session.add(ProjectTask(
                        tenant_id=uuid(tid), phase_id=phase.id, code=code,
                        name_ar=name_, planned_cost=cost, progress_pct=progress,
                        status=status, created_by=uuid(actor),
                        updated_by=uuid(actor)))
                db.session.commit()
                note("project tasks", f"{len(tasks)} tasks in PH-1")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("project tasks", f"skipped ({exc})")

        # ---------------------------------------- purchase agreement & recurring
        try:
            from app.models.addons import PurchaseAgreement, PurchaseAgreementLine
            from app.models.ops import RecurringEntry
            from app.services import sequence_service

            if not q("SELECT id FROM purchase_agreements WHERE tenant_id=:t", t=tid):
                number = sequence_service.next_doc_number(
                    tenant_id=uuid(tid), entity_id=uuid(eid),
                    doctype="purchase_agreement", year=2026)
                agr = PurchaseAgreement(
                    tenant_id=uuid(tid), entity_id=uuid(eid), doc_number=number,
                    supplier_id=uuid(supp_ids["S-002"]),
                    start_on=date(2026, 5, 1), ends_on=date(2026, 12, 31),
                    status="confirmed",
                    notes="اتفاقية توريد سنوية بأسعار ثابتة",
                    created_by=uuid(actor), updated_by=uuid(actor))
                db.session.add(agr)
                db.session.flush()
                for i, (product, qty, price) in enumerate(
                        [("P-001", 50, 58), ("P-003", 100, 39)], 1):
                    db.session.add(PurchaseAgreementLine(
                        tenant_id=uuid(tid), agreement_id=agr.id, line_number=i,
                        product_id=uuid(prod[product]),
                        qty=qty, unit_price=price,
                        created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("purchase agreement", f"{number} confirmed 6,800")

            if not q("SELECT id FROM recurring_entries WHERE tenant_id=:t", t=tid):
                db.session.add(RecurringEntry(
                    tenant_id=uuid(tid), entity_id=uuid(eid), code="REC-RENT-1",
                    description="إيجار المكتب الشهري", journal_id=uuid(j_gen),
                    frequency="monthly", next_run_on=date(2026, 11, 1),
                    template={"lines": [
                        {"account_id": acct("5120"), "debit": 900, "credit": 0},
                        {"account_id": acct("102001"), "debit": 0, "credit": 900},
                    ]}, is_active=True, created_by=uuid(actor),
                    updated_by=uuid(actor)))
                db.session.commit()
                note("recurring entry", "REC-RENT-1 monthly 900 from 2026-11-01")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("agreements/recurring", f"skipped ({exc})")

        # ------------------------------------------------------------ stock count
        if q("SELECT id FROM stock_counts WHERE entity_id=:e", e=eid):
            note("stock count", "present")
        else:
            from app.services import count_service
            try:
                c = count_service.create_count(
                    tenant_id=tid, entity_id=eid, warehouse_id=uuid(wh),
                    count_date=date(2026, 5, 20), actor_id=uuid(actor))
                count_service.snapshot(uuid(c.id), actor_id=uuid(actor))
                count_service.start(uuid(c.id), actor_id=uuid(actor))
                from app.models.product import StockCountLine
                lines = [{"line_id": str(l.id), "counted_qty": float(l.system_qty)}
                         for l in db.session.query(StockCountLine).filter_by(
                             count_id=c.id, is_deleted=False).all()]
                if lines:
                    count_service.submit(uuid(c.id), items=lines, actor_id=uuid(actor))
                    count_service.approve(uuid(c.id), actor_id=uuid(actor))
                    note("stock count",
                         f"{len(lines)} lines counted and approved (no variance)")
                else:
                    count_service.approve(uuid(c.id), actor_id=uuid(actor))
                    note("stock count", "created with no lines")
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                note("stock count", f"skipped ({exc})")

        # ---------------------------------------------------------- report schedule
        if not q("SELECT id FROM report_schedules WHERE entity_id=:e", e=eid):
            db.session.execute(text(
                "INSERT INTO report_schedules(tenant_id,entity_id,report_code,cron,"
                "is_active,created_by,updated_by)"
                " VALUES(:t,:e,'trial-balance','0 7 * * 1',TRUE,:a,:a)"
                " ON CONFLICT DO NOTHING"),
                dict(t=tid, e=eid, a=actor))
            db.session.execute(text(
                "INSERT INTO report_schedules(tenant_id,entity_id,report_code,cron,"
                "is_active,created_by,updated_by)"
                " VALUES(:t,:e,'aging-receivables','0 8 1 * *',TRUE,:a,:a)"
                " ON CONFLICT DO NOTHING"),
                dict(t=tid, e=eid, a=actor))
            db.session.commit()
            note("report schedules", "weekly trial balance + monthly aging")

        # ------------------------------------------------------- tax return & alerts
        try:
            from app.models.ops import Notification, TaxReturn
            from app.services import ops_service

            tax = q("SELECT id FROM taxes WHERE tenant_id=:t AND is_active=TRUE "
                    "ORDER BY created_at LIMIT 1", t=tid)
            if tax and not q("SELECT id FROM tax_returns WHERE tenant_id=:t", t=tid):
                for period in ("2026-01", "2026-02"):
                    ret = ops_service.file_tax_return(
                        tenant_id=tid, entity_id=eid, tax_id=tax,
                        period_code=period, actor_id=uuid(actor))
                    note("tax return",
                         f"{ret.period_code} filed net_due={ret.net_due}")

            if not q("SELECT id FROM notifications WHERE tenant_id=:t", t=tid):
                db.session.add(Notification(
                    tenant_id=uuid(tid), user_id=uuid(actor),
                    title="فاتورة متأخرة السداد",
                    body="الفاتورة INV-2026-0001 تجاوزت تاريخ الاستحقاق — يلزم متابعة العميل.",
                    severity="warning", is_read=False,
                    link_url="/sales/invoices",
                    created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.add(Notification(
                    tenant_id=uuid(tid), user_id=uuid(actor),
                    title="تنبيه مخزون",
                    body="رصيد الصنف P-002 قارب على النفاد — راجع حركة المخزون.",
                    severity="info", is_read=False,
                    link_url="/inventory",
                    created_by=uuid(actor), updated_by=uuid(actor)))
                db.session.commit()
                note("notifications", "2 demo alerts (overdue invoice + stock)")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            note("tax return/notifications", f"skipped ({exc})")

        db.session.commit()
        print("SEED_DEMO_FULL_OK")
    return 0


def uuid(s):
    import uuid as _u
    return _u.UUID(str(s))


if __name__ == "__main__":
    sys.exit(main() or 0)
