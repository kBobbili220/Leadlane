from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Computed, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RecordMixin

if TYPE_CHECKING:
    from .business import Business
    from .inquiry import Inquiry
    from .quote_item import QuoteItem


class Quote(RecordMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint("revision > 0"),
        CheckConstraint("status IN ('draft', 'sent', 'accepted', 'declined', 'expired', 'superseded', 'cancelled')"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'"),
        CheckConstraint("btrim(recipient_name) <> ''"),
        CheckConstraint("recipient_email IS NULL OR btrim(recipient_email) <> ''"),
        CheckConstraint("recipient_phone IS NULL OR btrim(recipient_phone) <> ''"),
        CheckConstraint("jsonb_typeof(vehicle_snapshot) = 'object'"),
        CheckConstraint("jsonb_typeof(service_address_snapshot) = 'object'"),
        CheckConstraint("subtotal_minor >= 0"),
        CheckConstraint("discount_minor >= 0"),
        CheckConstraint("tax_minor >= 0"),
        CheckConstraint("octet_length(public_token_hash) = 32"),
        CheckConstraint("follow_up_count >= 0"),
        UniqueConstraint("business_id", "id", name="quotes_tenant_id"),
        UniqueConstraint("business_id", "inquiry_id", "revision", name="quotes_revision"),
        ForeignKeyConstraint(["business_id", "inquiry_id"], ["inquiries.business_id", "inquiries.id"], name="quotes_inquiry_fk", ondelete="RESTRICT"),
        CheckConstraint("recipient_email IS NOT NULL OR recipient_phone IS NOT NULL", name="quotes_recipient_reachable"),
        CheckConstraint("discount_minor <= subtotal_minor", name="quotes_discount_limit"),
        CheckConstraint(
            "status NOT IN ('sent', 'accepted', 'declined', 'expired') OR "
            "(sent_at IS NOT NULL AND public_token_hash IS NOT NULL AND expires_at IS NOT NULL)",
            name="quotes_sent_link",
        ),
        CheckConstraint("status <> 'draft' OR sent_at IS NULL", name="quotes_draft_unsent"),
        CheckConstraint("expires_at > sent_at", name="quotes_expiry_order"),
        CheckConstraint("(status = 'accepted') = (accepted_at IS NOT NULL)", name="quotes_acceptance_state"),
        CheckConstraint("(status = 'declined') = (declined_at IS NOT NULL)", name="quotes_decline_state"),
        CheckConstraint(
            "(accepted_at IS NULL OR (accepted_at >= sent_at AND accepted_at < expires_at)) AND "
            "(declined_at IS NULL OR (declined_at >= sent_at AND declined_at < expires_at))",
            name="quotes_response_order",
        ),
        CheckConstraint("next_follow_up_at IS NULL OR status = 'sent'", name="quotes_follow_up_state"),
        Index("quotes_inquiry_idx", "business_id", "inquiry_id", text("created_at DESC"), text("id DESC")),
        Index("quotes_one_accepted_per_inquiry", "business_id", "inquiry_id", unique=True, postgresql_where=text("status = 'accepted'")),
        Index("quotes_follow_up_due_idx", "next_follow_up_at", "id", postgresql_where=text("status = 'sent' AND next_follow_up_at IS NOT NULL")),
        Index("quotes_expiry_due_idx", "expires_at", "id", postgresql_where=text("status = 'sent'")),
    )

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"))
    inquiry_id: Mapped[UUID]
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"))
    currency: Mapped[str] = mapped_column(String(3))
    recipient_name: Mapped[str] = mapped_column(String(200))
    recipient_email: Mapped[str | None] = mapped_column(String(254))
    recipient_phone: Mapped[str | None] = mapped_column(String(32))
    vehicle_snapshot: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb"))
    service_address_snapshot: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB), server_default=text("'{}'::jsonb"))
    customer_notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    discount_minor: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    tax_minor: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    total_minor: Mapped[int] = mapped_column(
        BigInteger, Computed("subtotal_minor - discount_minor + tax_minor", persisted=True), nullable=True
    )
    public_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(Text)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    business: Mapped[Business] = relationship(back_populates="quotes", foreign_keys=[business_id], lazy="raise")
    inquiry: Mapped[Inquiry] = relationship(
        primaryjoin="and_(Quote.business_id == Inquiry.business_id, foreign(Quote.inquiry_id) == Inquiry.id)",
        back_populates="quotes", lazy="raise",
    )
    items: Mapped[list[QuoteItem]] = relationship(
        primaryjoin="and_(Quote.business_id == QuoteItem.business_id, Quote.id == foreign(QuoteItem.quote_id))",
        back_populates="quote", order_by="QuoteItem.position", cascade="all, delete-orphan",
        passive_deletes=True, lazy="raise",
    )
