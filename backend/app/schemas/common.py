"""Shared API validation; database-generated and tenant IDs are output-only."""

from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints

BIGINT_MAX = 2**63 - 1
INTEGER_MAX = 2**31 - 1

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
UnitLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Currency = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
Money = Annotated[int, Field(strict=True, ge=0, le=BIGINT_MAX)]
PositiveInteger = Annotated[int, Field(strict=True, gt=0, le=INTEGER_MAX)]
NonNegativeInteger = Annotated[int, Field(strict=True, ge=0, le=INTEGER_MAX)]
JsonObject = dict[str, JsonValue]


class InquiryStatus(str, Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


class QuoteStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class PreferredChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RecordRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime
