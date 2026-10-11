"""Parties models (Phase 5 subset): unified party + addresses + contacts."""
from __future__ import annotations
import uuid
import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Date, Boolean, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from .base import (
    Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin,
)


class Party(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "parties"
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    legal_type: Mapped[str] = mapped_column(String(30), default="company", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credit_limit: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    credit_currency: Mapped[str] = mapped_column(String(3), default="JOD", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    addresses: Mapped[list["PartyAddress"]] = relationship(back_populates="party", cascade="all, delete-orphan")
    contacts: Mapped[list["PartyContact"]] = relationship(back_populates="party", cascade="all, delete-orphan")


class PartyAddress(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "party_addresses"
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    address_type: Mapped[str] = mapped_column(String(20), default="primary", nullable=False)
    address1: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str | None] = mapped_column(String(150))
    country: Mapped[str] = mapped_column(String(2), default="JO", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    party: Mapped["Party"] = relationship(back_populates="addresses")


class PartyContact(Base, PKMixin, TenantMixin, TimestampMixin, AuditMixin, VersionMixin, SoftDeleteMixin):
    __tablename__ = "party_contacts"
    party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    contact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    party: Mapped["Party"] = relationship(back_populates="contacts")
