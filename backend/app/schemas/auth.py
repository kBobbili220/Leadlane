from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, EmailStr, Field, SecretStr, field_validator

from .common import APIModel, Currency, Name


class LoginRequest(APIModel):
    email: Annotated[EmailStr, Field(max_length=254)]
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RegisterRequest(LoginRequest):
    password: SecretStr = Field(min_length=12, max_length=128)
    full_name: Name
    business_name: Name


class OwnerRead(APIModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str
    email: str


class OwnerBusinessRead(APIModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    currency: Currency
    timezone: str


class AuthIdentityRead(APIModel):
    user: OwnerRead
    business: OwnerBusinessRead
    role: Literal["owner"] = "owner"
    expires_at: AwareDatetime


class AuthTokenRead(AuthIdentityRead):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
