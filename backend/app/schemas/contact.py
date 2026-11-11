from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, model_validator

from .common import APIModel, Email, Name, Phone, PreferredChannel, RecordRead


class ContactFields(APIModel):
    name: Name
    email: Email | None = None
    phone: Phone | None = None
    preferred_channel: PreferredChannel | None = None

    @model_validator(mode="after")
    def reachable(self) -> ContactFields:
        if self.email is None and self.phone is None:
            raise ValueError("email or phone is required")
        if self.preferred_channel == PreferredChannel.EMAIL and self.email is None:
            raise ValueError("email is required for the email channel")
        if self.preferred_channel in (PreferredChannel.SMS, PreferredChannel.PHONE) and self.phone is None:
            raise ValueError("phone is required for the sms/phone channel")
        return self


class PublicContactCreate(ContactFields):
    pass


class ContactCreate(ContactFields):
    notes: str | None = None


class ContactRead(ContactCreate, RecordRead):
    business_id: UUID
    archived_at: AwareDatetime | None = None
