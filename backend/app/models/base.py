"""Shared mapping for the PostgreSQL migration's generated fields."""

from datetime import datetime
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, FetchedValue, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RecordMixin:
    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"),
        server_onupdate=FetchedValue(), nullable=False,
    )
    # Fetch timestamp values maintained by the migration's UPDATE triggers.
    __mapper_args__ = {"eager_defaults": True}
