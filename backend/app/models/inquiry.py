from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .business import Business
    from .contact import Contact
    from .quote import Quote
    from .service import Service


class Inquiry(RecordMixin, Base):
    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'reviewing', 'quoted', 'won', 'lost', 'cancelled')"),
        CheckConstraint("vehicle_year BETWEEN 1886 AND 2200"),
        CheckConstraint("jsonb_typeof(vehicle_details) = 'object'"),
        CheckConstraint("jsonb_typeof(service_address) = 'object'"),
        UniqueConstraint("business_id", "id", name="inquiries_tenant_id"),
        UniqueConstraint("business_id", "submission_key", name="inquiries_submission_key"),
        ForeignKeyConstraint(["business_id", "contact_id"], ["contacts.business_id", "contacts.id"], name="inquiries_contact_fk", ondelete="RESTRICT"),
        ForeignKeyConstraint(["business_id", "requested_service_id"], ["services.business_id", "services.id"], name="inquiries_service_fk", ondelete="RESTRICT"),
        CheckConstraint(
            "preferred_end_at IS NULL OR (preferred_start_at IS NOT NULL AND preferred_end_at > preferred_start_at)",
            name="inquiries_preferred_window",
        ),
        CheckConstraint("(status IN ('won', 'lost', 'cancelled')) = (closed_at IS NOT NULL)", name="inquiries_closed_state"),
        Index("inquiries_inbox_idx", "business_id", text("created_at DESC"), text("id DESC")),
        Index("inquiries_status_idx", "business_id", "status", text("created_at DESC"), text("id DESC")),
        Index("inquiries_contact_idx", "business_id", "contact_id", text("created_at DESC")),
        Index("inquiries_service_idx", "business_id", "requested_service_id", postgresql_where=text("requested_service_id IS NOT NULL")),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    contact_id: Mapped[UUID]
    requested_service_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(20), server_default=text("'new'"))
    source: Mapped[str] = mapped_column(String(50), server_default=text("'public_form'"))
    message: Mapped[str | None] = mapped_column(Text)
    vehicle_year: Mapped[int | None] = mapped_column(SmallInteger)
    vehicle_make: Mapped[str | None] = mapped_column(String(100))
    vehicle_model: Mapped[str | None] = mapped_column(String(100))
    vehicle_size: Mapped[str | None] = mapped_column(String(50))
    vehicle_details: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb"))
    service_address: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb"))
    preferred_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    internal_notes: Mapped[str | None] = mapped_column(Text)
    lost_reason: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_key: Mapped[str | None] = mapped_column(String(128))

    business: Mapped[Business] = relationship(back_populates="inquiries", foreign_keys=[business_id], lazy="raise")
    contact: Mapped[Contact] = relationship(
        primaryjoin="and_(Inquiry.business_id == Contact.business_id, foreign(Inquiry.contact_id) == Contact.id)",
        back_populates="inquiries", lazy="raise",
    )
    requested_service: Mapped[Service | None] = relationship(
        primaryjoin="and_(Inquiry.business_id == Service.business_id, foreign(Inquiry.requested_service_id) == Service.id)",
        back_populates="requested_inquiries", lazy="raise",
    )
    quotes: Mapped[list[Quote]] = relationship(
        primaryjoin="and_(Inquiry.business_id == Quote.business_id, Inquiry.id == foreign(Quote.inquiry_id))",
        back_populates="inquiry", passive_deletes="all", lazy="raise",
    )
