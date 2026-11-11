from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .business import Business
    from .inquiry import Inquiry
    from .quote_item import QuoteItem


class Service(RecordMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''"),
        CheckConstraint("base_price_minor >= 0"),
        CheckConstraint("estimated_duration_minutes > 0"),
        CheckConstraint("btrim(unit_label) <> ''"),
        UniqueConstraint("business_id", "id", name="services_tenant_id"),
        Index("services_catalog_idx", "business_id", "is_active", "sort_order", "id"),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    base_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    unit_label: Mapped[str] = mapped_column(String(50), server_default=text("'vehicle'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    business: Mapped[Business] = relationship(back_populates="services", lazy="raise")
    requested_inquiries: Mapped[list[Inquiry]] = relationship(
        primaryjoin="and_(Service.business_id == Inquiry.business_id, Service.id == foreign(Inquiry.requested_service_id))",
        back_populates="requested_service", passive_deletes="all", lazy="raise",
    )
    quote_items: Mapped[list[QuoteItem]] = relationship(
        primaryjoin="and_(Service.business_id == QuoteItem.business_id, Service.id == foreign(QuoteItem.service_id))",
        back_populates="service", passive_deletes="all", lazy="raise",
    )
