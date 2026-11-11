from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, RecordMixin


class User(RecordMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("btrim(full_name) <> ''"),
        CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="users_email_normalized"),
    )
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class BusinessMembership(RecordMixin, Base):
    __tablename__ = "business_memberships"
    __table_args__ = (CheckConstraint("role = 'owner'"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"), unique=True)
    role: Mapped[str] = mapped_column(String(20), server_default=text("'owner'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class AuthSession(RecordMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("octet_length(token_digest) = 32"),
        CheckConstraint("expires_at > created_at", name="auth_sessions_expiry"),
        Index("auth_sessions_membership_idx", "membership_id"),
        Index("auth_sessions_expiry_idx", "expires_at"),
    )
    membership_id: Mapped[UUID] = mapped_column(ForeignKey("business_memberships.id", ondelete="CASCADE"))
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (
        CheckConstraint("octet_length(key_digest) = 32"),
        CheckConstraint("attempts > 0"),
        Index("auth_rate_limits_window_idx", "window_start"),
    )
    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    key_digest: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
