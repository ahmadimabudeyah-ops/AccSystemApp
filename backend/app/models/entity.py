"""Entity / branch / group models (Phase 1, group C + Phase 2 fiscal)."""
import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Boolean, ForeignKey
from .base import Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin


class Entity(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "entities"
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    functional_currency: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    branches: Mapped[list["Branch"]] = relationship(back_populates="entity")


class Branch(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "branches"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    entity: Mapped["Entity"] = relationship(back_populates="branches")


class FiscalYear(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "fiscal_years"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    starts_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="future", nullable=False)


class FiscalPeriod(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "fiscal_periods"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    fiscal_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    period_number: Mapped[int] = mapped_column(nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))
    starts_on: Mapped[Date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="future", nullable=False)
