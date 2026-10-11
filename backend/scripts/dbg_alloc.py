"""Debug allocate in-process."""
import sys
import uuid

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import text  # noqa: E402

app = create_app()
with app.app_context():
    db.session.execute(
        text("SET app.current_tenant_id = 'b39787b5-52fb-4fb0-b41f-98b90b5853d6'"))
    from app.models.user import User  # noqa: E402
    from app.models.sales import CustomerPayment  # noqa: E402
    from app.services import sales_service  # noqa: E402
    checker = db.session.query(User).filter_by(email="checker@demo.local").first()
    pay = (db.session.query(CustomerPayment)
           .order_by(CustomerPayment.created_at.desc()).first())
    print("PAY", pay.id, pay.status, pay.unallocated_amount)
    inv_id = None
    from app.models.sales import CustomerInvoice  # noqa: E402
    inv = (db.session.query(CustomerInvoice)
           .filter_by(status="posted").order_by(CustomerInvoice.created_at.desc()).first())
    print("INV", inv.id if inv else None, inv.status if inv else None)
    try:
        r = sales_service.allocate(
            payment_id=pay.id,
            allocations=[{"invoice_id": inv.id, "allocated_amount": 232}],
            actor_id=checker.id)
        print("ALLOCATED", r.allocated_amount, r.unallocated_amount)
    except Exception:
        import traceback  # noqa: E402
        traceback.print_exc()
