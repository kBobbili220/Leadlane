"""Owner account creation, session management, and business authorization.

Routers validate request schemas and enforce rate limits before calling register
or login. This module commits successful account/session changes; request-scoped
session cleanup rolls back unfinished work when an exception escapes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
import secrets
import unicodedata

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.core.security import dummy_password_hash, password_hasher, token_digest, verify_password
from backend.app.models import AuthRateLimit, AuthSession, Business, BusinessMembership, User
from backend.app.schemas.auth import AuthIdentityRead, AuthTokenRead, OwnerBusinessRead, OwnerRead, RegisterRequest


@dataclass
class OwnerContext:
    """Verified records used to scope an owner's requests to their business."""

    user: User
    membership: BusinessMembership
    business: Business
    session: AuthSession


def unauthorized() -> HTTPException:
    """Use the same Bearer challenge for missing, invalid, or expired sessions."""
    return HTTPException(401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"})


def enforce_rate_limits(session: Session, limits: list[tuple[str, str, int, int]]) -> None:
    """Commit counters even when the authentication operation will fail.

    Upserts serialize increments across workers. This runs before any account or
    session changes, so committing counters cannot commit a partial registration.
    Each limit is (scope, email_or_ip_key, maximum_attempts, window_seconds).
    """
    now = datetime.now(timezone.utc)
    # Retain recent windows for enforcement without accumulating them forever.
    session.execute(delete(AuthRateLimit).where(AuthRateLimit.window_start < now - timedelta(days=1)))
    insert = postgres_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    retry_after = 0
    for scope, key, maximum, seconds in limits:
        # Align requests to a shared fixed window, rather than starting a new
        # window for every attempt. Only a digest of the email/IP is persisted.
        start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, timezone.utc)
        statement = insert(AuthRateLimit).values(
            scope=scope, key_digest=token_digest(key), window_start=start, attempts=1
        ).on_conflict_do_update(
            index_elements=["scope", "key_digest", "window_start"],
            set_={"attempts": AuthRateLimit.attempts + 1},
        ).returning(AuthRateLimit.attempts)
        attempts = session.scalar(statement)
        if attempts > maximum:
            # If multiple limits apply, wait until all exceeded windows reset.
            retry_after = max(retry_after, math.ceil((start + timedelta(seconds=seconds) - now).total_seconds()))
    session.commit()
    if retry_after:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(retry_after)})


def identity(context: OwnerContext) -> AuthIdentityRead:
    """Project verified records into response fields that exclude stored secrets."""
    expires = context.session.expires_at
    # PostgreSQL returns aware timestamptz values; SQLite HTTP test fixtures do not.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return AuthIdentityRead(
        user=OwnerRead.model_validate(context.user),
        business=OwnerBusinessRead.model_validate(context.business),
        role=context.membership.role,
        expires_at=expires,
    )


def issue_session(session: Session, user: User, membership: BusinessMembership, business: Business, settings: Settings) -> AuthTokenRead:
    """Create a session inside the caller's transaction and return its raw token."""
    # The random token is the client's credential. Persist only its digest so a
    # database read cannot directly reveal reusable bearer tokens.
    raw_token = secrets.token_urlsafe(32)
    record = AuthSession(
        membership_id=membership.id, token_digest=token_digest(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.auth_session_ttl_days),
    )
    session.add(record)
    # Fetch database-generated fields without committing the caller's transaction.
    session.flush()
    safe = identity(OwnerContext(user, membership, business, record))
    return AuthTokenRead(**safe.model_dump(), access_token=raw_token)


def register(session: Session, payload: RegisterRequest, settings: Settings) -> AuthTokenRead:
    """Create an owner, new business, membership, and initial session atomically."""
    # Public registration always creates a new business; no caller can claim an
    # existing business by submitting an ID, slug or DEV_BUSINESS_ID.
    slug_name = unicodedata.normalize("NFKD", payload.business_name).encode("ascii", "ignore").decode()
    # Normalize public slugs and reduce collisions between identically named shops.
    slug_name = re.sub(r"[^a-z0-9]+", "-", slug_name.lower()).strip("-")[:90].rstrip("-") or "business"
    business = Business(name=payload.business_name, slug=f"{slug_name}-{secrets.token_hex(4)}")
    user = User(email=str(payload.email), full_name=payload.full_name,
                password_hash=password_hasher.hash(payload.password.get_secret_value()))
    try:
        session.add_all([business, user])
        session.flush()
        membership = BusinessMembership(user_id=user.id, business_id=business.id)
        session.add(membership)
        session.flush()
        response = issue_session(session, user, membership, business, settings)
        session.commit()
        return response
    except IntegrityError:
        # Uniqueness constraints handle concurrent sign-ups too. Roll back the
        # business as well as the user, and do not disclose constraint details.
        session.rollback()
        raise HTTPException(409, "Unable to create an account with these details") from None


def login(session: Session, email: str, password: str, settings: Settings) -> AuthTokenRead:
    """Verify normalized credentials and issue a separate session for this login."""
    user = session.scalar(select(User).where(User.email == email))
    # Unknown emails still perform password verification against a dummy hash.
    # Keep their error identical to wrong-password and disabled-account errors.
    valid, replacement_hash = verify_password(password, user.password_hash if user else dummy_password_hash)
    if not valid or user is None or not user.is_active:
        raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    row = session.execute(
        select(BusinessMembership, Business)
        .join(Business, Business.id == BusinessMembership.business_id)
        .where(BusinessMembership.user_id == user.id)
    ).one_or_none()
    if row is None or not row[0].is_active or not row[1].is_active or row[0].role != "owner":
        raise HTTPException(403, "Business access is unavailable")
    if replacement_hash:
        # Upgrade older password-hash settings after successful verification.
        user.password_hash = replacement_hash
    response = issue_session(session, user, row[0], row[1], settings)
    session.commit()
    return response


def authenticate(session: Session, raw_token: str) -> OwnerContext:
    """Resolve a bearer credential and recheck account/business access per request."""
    # Resolve the business through the session's membership. Client-provided
    # business IDs cannot select another tenant. Expiry uses database time.
    row = session.execute(
        select(AuthSession, BusinessMembership, User, Business)
        .join(BusinessMembership, BusinessMembership.id == AuthSession.membership_id)
        .join(User, User.id == BusinessMembership.user_id)
        .join(Business, Business.id == BusinessMembership.business_id)
        .where(AuthSession.token_digest == token_digest(raw_token),
               AuthSession.revoked_at.is_(None), AuthSession.expires_at > func.now())
    ).one_or_none()
    if row is None or not row[2].is_active:
        raise unauthorized()
    record, membership, user, business = row
    # A valid session alone is insufficient if business access has been disabled.
    if not membership.is_active or not business.is_active or membership.role != "owner":
        raise HTTPException(403, "Business access is unavailable")
    return OwnerContext(user, membership, business, record)


def logout(session: Session, raw_token: str) -> None:
    """Revoke only the presented session; repeated logout calls remain safe."""
    # Do not require an active account/membership here: revoked or expired tokens
    # should still be harmless to submit, and other device sessions stay active.
    session.execute(update(AuthSession).where(
        AuthSession.token_digest == token_digest(raw_token), AuthSession.revoked_at.is_(None)
    ).values(revoked_at=datetime.now(timezone.utc)))
    session.commit()
