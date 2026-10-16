"""Products + inventory models (Phase 6 subset)."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite,
)


class ProductCategory(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "product_categories"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_categories.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UoM(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "uoms"
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    factor: Mapped[float] = mapped_column(Numeric(18, 10), default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "products"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    product_type: Mapped[str] = mapped_column(String(30), default="stockable", nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_categories.id", ondelete="RESTRICT"))
    base_uom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uoms.id", ondelete="RESTRICT"))
    cost_method: Mapped[str] = mapped_column(String(20), default="average", nullable=False)
    standard_cost: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Warehouse(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "warehouses"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Location(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "locations"
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StockQuant(Base, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    """كاش الأرصدة — مفتاح مركب (product, location) | Composite PK."""
    __tablename__ = "stock_quants"
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True)
    variant_id: Mapped[uuid.UUID | None]
    qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    reserved_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)


class StockMove(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "stock_moves"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uoms.id", ondelete="RESTRICT"), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    dest_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    move_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    move_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id", ondelete="RESTRICT"))


class StockCount(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    """رأس الجرد الفعلي: draft → counting → approved → posted (تسويات)."""
    __tablename__ = "stock_counts"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    count_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class StockCountLine(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteLite):
    __tablename__ = "stock_count_lines"
    count_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stock_counts.id", ondelete="CASCADE"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    system_qty: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    counted_qty: Mapped[float | None] = mapped_column(Numeric(18, 6))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 6), default=0, nullable=False)
