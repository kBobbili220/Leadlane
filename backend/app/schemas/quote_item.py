from __future__ import annotations

from uuid import UUID

from pydantic import ConfigDict, model_validator

from .common import APIModel, BIGINT_MAX, Money, Name, NonNegativeInteger, PositiveInteger, RecordRead, UnitLabel


class QuoteItemFields(APIModel):
    position: NonNegativeInteger
    name: Name
    description: str | None = None
    unit_label: UnitLabel = "vehicle"
    quantity: PositiveInteger = 1
    unit_price_minor: Money
    estimated_duration_minutes: PositiveInteger | None = None

    @model_validator(mode="after")
    def line_total_fits_bigint(self) -> QuoteItemFields:
        if self.quantity * self.unit_price_minor > BIGINT_MAX:
            raise ValueError("line total exceeds PostgreSQL bigint range")
        return self


class QuoteItemCreate(QuoteItemFields):
    service_id: UUID | None = None


class QuoteItemRead(QuoteItemCreate, RecordRead):
    business_id: UUID
    quote_id: UUID
    line_total_minor: Money


class PublicQuoteItemRead(QuoteItemFields):
    model_config = ConfigDict(from_attributes=True)

    line_total_minor: Money
