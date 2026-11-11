from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .business import Business
    from .inquiry import Inquiry


class Contact(RecordMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''"),
        CheckConstraint("email IS NULL OR btrim(email) <> ''"),
        CheckConstraint("phone IS NULL OR btrim(phone) <> ''"),
        CheckConstraint("preferred_channel IN ('email', 'sms', 'phone')"),
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="contacts_reachable"),
        CheckConstraint(
            "(preferred_channel <> 'email' OR email IS NOT NULL) AND "
            "(preferred_channel NOT IN ('sms', 'phone') OR phone IS NOT NULL)",
            name="contacts_channel_available",
        ),
        UniqueConstraint("business_id", "id", name="contacts_tenant_id"),
        Index("contacts_email_idx", "business_id", text("lower(email)"), postgresql_where=text("email IS NOT NULL")),
        Index("contacts_phone_idx", "business_id", "phone", postgresql_where=text("phone IS NOT NULL")),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_channel: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    business: Mapped[Business] = relationship(back_populates="contacts", lazy="raise")
    inquiries: Mapped[list[Inquiry]] = relationship(
        primaryjoin="and_(Contact.business_id == Inquiry.business_id, Contact.id == foreign(Inquiry.contact_id))",
        back_populates="contact", passive_deletes="all", lazy="raise",
    )
