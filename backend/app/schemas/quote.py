from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from .common import APIModel, BIGINT_MAX, Currency, Email, JsonObject, Money, Name, NonNegativeInteger, Phone, PositiveInteger, QuoteStatus, RecordRead
from .quote_item import PublicQuoteItemRead, QuoteItemCreate, QuoteItemRead


class QuoteFields(APIModel):
    currency: Currency
    recipient_name: Name
    recipient_email: Email | None = None
    recipient_phone: Phone | None = None
    vehicle_snapshot: JsonObject = Field(default_factory=dict)
    service_address_snapshot: JsonObject = Field(default_factory=dict)
    customer_notes: str | None = None
    terms: str | None = None

    @model_validator(mode="after")
    def recipient_reachable(self) -> QuoteFields:
        if self.recipient_email is None and self.recipient_phone is None:
            raise ValueError("recipient_email or recipient_phone is required")
        return self


class QuoteCreate(QuoteFields):
    """Draft content. Tenant, inquiry, revision, status and totals come from the server."""

    discount_minor: Money = 0
    tax_minor: Money = 0
    items: list[QuoteItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_items_and_amounts(self) -> QuoteCreate:
        positions = [item.position for item in self.items]
        if len(set(positions)) != len(positions):
            raise ValueError("item positions must be unique within a quote")
        subtotal = sum(item.quantity * item.unit_price_minor for item in self.items)
        if self.discount_minor > subtotal:
            raise ValueError("discount cannot exceed the item subtotal")
        if subtotal > BIGINT_MAX or subtotal - self.discount_minor + self.tax_minor > BIGINT_MAX:
            raise ValueError("quote amount exceeds PostgreSQL bigint range")
        return self


class QuoteSummaryRead(QuoteFields, RecordRead):
    """Owner-facing header; token digests are deliberately excluded."""

    business_id: UUID
    inquiry_id: UUID
    revision: PositiveInteger
    status: QuoteStatus
    subtotal_minor: Money
    discount_minor: Money
    tax_minor: Money
    total_minor: Money
    sent_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    viewed_at: AwareDatetime | None = None
    accepted_at: AwareDatetime | None = None
    declined_at: AwareDatetime | None = None
    decline_reason: str | None = None
    next_follow_up_at: AwareDatetime | None = None
    last_follow_up_at: AwareDatetime | None = None
    follow_up_count: NonNegativeInteger


class QuoteRead(QuoteSummaryRead):
    items: list[QuoteItemRead]


class PublicQuoteRead(APIModel):
    """Explicit public projection; no tenant/contact IDs or worker metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: QuoteStatus
    currency: Currency
    recipient_name: Name
    vehicle_snapshot: JsonObject
    service_address_snapshot: JsonObject
    customer_notes: str | None = None
    terms: str | None = None
    subtotal_minor: Money
    discount_minor: Money
    tax_minor: Money
    total_minor: Money
    sent_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    accepted_at: AwareDatetime | None = None
    declined_at: AwareDatetime | None = None
    items: list[PublicQuoteItemRead]


class QuoteSendRequest(APIModel):
    expires_at: AwareDatetime


class QuoteAcceptanceRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: QuoteStatus
    accepted_at: AwareDatetime
