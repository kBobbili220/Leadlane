from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from .common import APIModel, INTEGER_MAX, Money, Name, PositiveInteger, RecordRead, UnitLabel


class ServiceFields(APIModel):
    name: Name
    description: str | None = None
    base_price_minor: Money | None = None
    estimated_duration_minutes: PositiveInteger | None = None
    unit_label: UnitLabel = "vehicle"
    is_active: bool = True
    sort_order: int = Field(default=0, strict=True, ge=-(2**31), le=INTEGER_MAX)


class ServiceCreate(ServiceFields):
    pass


class ServiceUpdate(APIModel):
    """Omitted fields stay unchanged; only nullable database columns accept null."""

    name: Name | None = Field(default=None, description="Omit to keep unchanged; null is not allowed.")
    description: str | None = None
    base_price_minor: Money | None = None
    estimated_duration_minutes: PositiveInteger | None = None
    unit_label: UnitLabel | None = Field(default=None, description="Omit to keep unchanged; null is not allowed.")
    is_active: bool | None = Field(default=None, description="Omit to keep unchanged; null is not allowed.")
    sort_order: int | None = Field(default=None, strict=True, ge=-(2**31), le=INTEGER_MAX,
                                   description="Omit to keep unchanged; null is not allowed.")

    @model_validator(mode="after")
    def valid_patch(self) -> ServiceUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")
        for name in ("name", "unit_label", "is_active", "sort_order"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ServiceRead(ServiceFields, RecordRead):
    business_id: UUID
