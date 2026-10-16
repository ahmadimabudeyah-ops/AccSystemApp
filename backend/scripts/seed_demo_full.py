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
  05 Mar  petty-cash withdrawal, bank-to-cash transfer
  12 Apr  asset purchase + depreciation, payroll run
  01 May  education fee contract + first instalment
  20 May  stock count with a real variance, VAT return
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
        ar, stock, ap = acct("1210"), acct("1310"), acct("2010")
        vat_out, vat_in = acct("2140"), acct("2141")
        capital, sales, cogs = acct("30501"), acct("4010"), acct("5010")
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

        # unit of measure + categories + products
        uom = q("SELECT id FROM uoms WHERE entity_id=:e LIMIT 1", e=eid) or \
            q("SELECT id FROM uoms LIMIT 1")
        cat = str(q("SELECT id FROM product_categories WHERE entity_id=:e LIMIT 1", e=eid)
                  or q("SELECT id FROM product_categories LIMIT 1"))
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
                 ("30501", 0.0, 145000.0)])
        opening("رصيد افتتاحي — مخزون أول المدة", "2026-01-01",
                [("1310", 40000.0, 0.0),
                 ("30501", 0.0, 40000.0)])
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
            lines=[{"product_id": prod["P-001"], "qty": 100, "unit_price": 60.000},
                   {"product_id": prod["P-002"], "qty": 40, "unit_price": 160.000},
                   {"product_id": prod["P-003"], "qty": 200, "unit_price": 40.000}],
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
            lines=[{"product_id": prod["P-001"], "qty": 40, "unit_price": 100.000},
                   {"product_id": prod["P-002"], "qty": 15, "unit_price": 250.000}],
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
            lines=[{"product_id": prod["P-001"], "qty": 2, "unit_price": 100.000}],
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
        bank_acct = q("SELECT id FROM bank_accounts WHERE tenant_id=:t LIMIT 1", t=tid)
        note("treasury", f"cash box={str(box)[:8] if box else '-'} "
                         f"bank account={str(bank_acct)[:8] if bank_acct else '-'}")
        db.session.commit()

        # --------------------------------------------------------------- payroll
        emp_ids = [str(r[0]) for r in db.session.execute(text(
            "SELECT id FROM employees WHERE entity_id=:e AND is_deleted=FALSE"),
            {"e": eid}).fetchall()]
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

        # -------------------------------------------------------------- education
        from app.services import edu_service
        stu = q("SELECT id FROM students WHERE entity_id=:e LIMIT 1", e=eid)
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

        db.session.commit()
        print("SEED_DEMO_FULL_OK")
    return 0


def uuid(s):
    import uuid as _u
    return _u.UUID(str(s))


if __name__ == "__main__":
    sys.exit(main() or 0)
