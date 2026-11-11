from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Computed, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .business import Business
    from .quote import Quote
    from .service import Service


class QuoteItem(RecordMixin, Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint("position >= 0"),
        CheckConstraint("btrim(name) <> ''"),
        CheckConstraint("btrim(unit_label) <> ''"),
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price_minor >= 0"),
        CheckConstraint("estimated_duration_minutes > 0"),
        UniqueConstraint("business_id", "quote_id", "position", name="quote_items_position"),
        ForeignKeyConstraint(["business_id", "quote_id"], ["quotes.business_id", "quotes.id"], name="quote_items_quote_fk", ondelete="CASCADE"),
        ForeignKeyConstraint(["business_id", "service_id"], ["services.business_id", "services.id"], name="quote_items_service_fk", ondelete="RESTRICT"),
        Index("quote_items_service_idx", "business_id", "service_id", postgresql_where=text("service_id IS NOT NULL")),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    quote_id: Mapped[UUID]
    service_id: Mapped[UUID | None]
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    unit_label: Mapped[str] = mapped_column(String(50), server_default=text("'vehicle'"))
    quantity: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    unit_price_minor: Mapped[int] = mapped_column(BigInteger)
    line_total_minor: Mapped[int] = mapped_column(
        BigInteger, Computed("quantity::bigint * unit_price_minor", persisted=True), nullable=True
    )
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)

    business: Mapped[Business] = relationship(back_populates="quote_items", foreign_keys=[business_id], lazy="raise")
    quote: Mapped[Quote] = relationship(
        primaryjoin="and_(QuoteItem.business_id == Quote.business_id, foreign(QuoteItem.quote_id) == Quote.id)",
        back_populates="items", lazy="raise",
    )
    service: Mapped[Service | None] = relationship(
        primaryjoin="and_(QuoteItem.business_id == Service.business_id, foreign(QuoteItem.service_id) == Service.id)",
        back_populates="quote_items", lazy="raise",
    )
