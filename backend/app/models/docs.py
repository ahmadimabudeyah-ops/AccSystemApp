"""Sales/purchase document models (quotes, orders, deliveries, receipts)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite,
)


class Quotation(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "quotations"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    quote_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[datetime.date | None] = mapped_column(Date)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["QuotationLine"]] = relationship(back_populates="quotation", cascade="all, delete-orphan")


class QuotationLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "quotation_lines"
    quotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    quotation: Mapped["Quotation"] = relationship(back_populates="lines")


class SalesOrder(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "sales_orders"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    currency_id: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quotations.id", ondelete="RESTRICT"))
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["SalesOrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class SalesOrderLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "sales_order_lines"
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    ordered_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    delivered_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    invoiced_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(7, 4), default=0, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    order: Mapped["SalesOrder"] = relationship(back_populates="lines")


class Delivery(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "deliveries"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sales_orders.id", ondelete="RESTRICT"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    delivery_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["DeliveryLine"]] = relationship(back_populates="delivery", cascade="all, delete-orphan")


class DeliveryLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "delivery_lines"
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    requested_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    delivered_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    source_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    delivery: Mapped["Delivery"] = relationship(back_populates="lines")


class PurchaseRequest(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "purchase_requests"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    request_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["PurchaseRequestLine"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class PurchaseRequestLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "purchase_request_lines"
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    request: Mapped["PurchaseRequest"] = relationship(back_populates="lines")


class PurchaseOrder(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "purchase_orders"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_requests.id", ondelete="RESTRICT"))
    order_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    grand_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "purchase_order_lines"
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    ordered_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


class GoodsReceipt(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "goods_receipts"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"))
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    receipt_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class GoodsReceiptLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "goods_receipt_lines"
    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    receipt: Mapped["GoodsReceipt"] = relationship(back_populates="lines")
