from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .contact import Contact
    from .inquiry import Inquiry
    from .quote import Quote
    from .quote_item import QuoteItem
    from .service import Service


class Business(RecordMixin, Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'"),
        CheckConstraint("jsonb_typeof(address) = 'object'"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="businesses_slug_format"),
    )

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(100), server_default=text("'UTC'"))
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'USD'"))
    address: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    contacts: Mapped[list[Contact]] = relationship(back_populates="business", passive_deletes="all", lazy="raise")
    services: Mapped[list[Service]] = relationship(back_populates="business", passive_deletes="all", lazy="raise")
    inquiries: Mapped[list[Inquiry]] = relationship(back_populates="business", passive_deletes="all", lazy="raise")
    quotes: Mapped[list[Quote]] = relationship(back_populates="business", passive_deletes="all", lazy="raise")
    quote_items: Mapped[list[QuoteItem]] = relationship(back_populates="business", passive_deletes="all", lazy="raise")
