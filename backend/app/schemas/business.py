from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from .common import APIModel, Currency, Email, JsonObject, Name, Phone, RecordRead


class BusinessFields(APIModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: Name
    email: Email | None = None
    phone: Phone | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    currency: Currency = "USD"
    address: JsonObject = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be an IANA timezone name") from exc
        return value


class BusinessCreate(BusinessFields):
    pass


class BusinessRead(BusinessFields, RecordRead):
    pass
