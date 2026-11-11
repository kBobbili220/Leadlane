from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from .common import APIModel, InquiryStatus, JsonObject, RecordRead
from .contact import ContactRead, PublicContactCreate
from .quote import QuoteSummaryRead
from .service import ServiceRead


class InquiryFields(APIModel):
    requested_service_id: UUID | None = None
    message: str | None = None
    vehicle_year: int | None = Field(default=None, strict=True, ge=1886, le=2200)
    vehicle_make: str | None = Field(default=None, max_length=100)
    vehicle_model: str | None = Field(default=None, max_length=100)
    vehicle_size: str | None = Field(default=None, max_length=50)
    vehicle_details: JsonObject = Field(default_factory=dict)
    service_address: JsonObject = Field(default_factory=dict)
    preferred_start_at: AwareDatetime | None = None
    preferred_end_at: AwareDatetime | None = None
    submission_key: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def valid_preferred_window(self) -> InquiryFields:
        if self.preferred_end_at is not None:
            if self.preferred_start_at is None or self.preferred_end_at <= self.preferred_start_at:
                raise ValueError("preferred_end_at requires an earlier preferred_start_at")
        return self


class PublicInquiryCreate(InquiryFields):
    """The slug determines the business; customers cannot set owner-only fields."""

    contact: PublicContactCreate


class InquiryCreate(InquiryFields):
    contact_id: UUID
    source: str = Field(default="public_form", max_length=50)
    internal_notes: str | None = None


class InquiryRead(InquiryCreate, RecordRead):
    business_id: UUID
    status: InquiryStatus
    lost_reason: str | None = None
    closed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_closed_state(self) -> InquiryRead:
        terminal = self.status in (InquiryStatus.WON, InquiryStatus.LOST, InquiryStatus.CANCELLED)
        if terminal != (self.closed_at is not None):
            raise ValueError("closed_at must be set exactly when the inquiry is terminal")
        return self


class InquiryDetailRead(InquiryRead):
    contact: ContactRead
    requested_service: ServiceRead | None = None
    quotes: list[QuoteSummaryRead]
