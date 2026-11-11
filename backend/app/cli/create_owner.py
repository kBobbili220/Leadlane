"""Attach the first owner to an existing business without modifying its services."""
import argparse
import getpass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import password_hasher
from backend.app.db.session import get_engine
from backend.app.models import Business, BusinessMembership, User
from backend.app.schemas.auth import RegisterRequest


def create_owner(session: Session, business_id: UUID, email: str, full_name: str, password: str) -> bool:
    # Reuse registration validation/canonicalization; business_name is not saved.
    payload = RegisterRequest(email=email, full_name=full_name, password=password, business_name="Existing business")
    business = session.scalar(select(Business).where(Business.id == business_id).with_for_update())
    if business is None or not business.is_active:
        raise ValueError("Business does not exist or is inactive")
    existing_membership = session.scalar(select(BusinessMembership).where(BusinessMembership.business_id == business_id))
    user = session.scalar(select(User).where(User.email == str(payload.email)))
    if existing_membership:
        if user and existing_membership.user_id == user.id and user.is_active and existing_membership.is_active:
            return False
        raise ValueError("This business already has an owner; ownership was not changed")
    if user is not None:
        raise ValueError("This email already belongs to an account; use a different email")
    try:
        user = User(email=str(payload.email), full_name=payload.full_name,
                    password_hash=password_hasher.hash(payload.password.get_secret_value()))
        session.add(user)
        session.flush()
        session.add(BusinessMembership(user_id=user.id, business_id=business.id))
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        raise ValueError("An owner/account was created concurrently; ownership was not changed") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first owner for an existing business")
    parser.add_argument("--business-id", required=True, type=UUID)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Owner password (12–128 characters): ")
    if password != getpass.getpass("Confirm password: "):
        print("Passwords did not match. Nothing was changed.")
        return 1
    settings = get_settings()
    if settings.database_url is None:
        print("DATABASE_URL is not configured.")
        return 1
    try:
        with Session(get_engine(settings.database_url.get_secret_value())) as session:
            created = create_owner(session, args.business_id, args.email, args.name, password)
        print("Owner created. Sign in using the mobile app." if created else "This owner is already linked. No password or ownership was changed.")
        return 0
    except ValidationError:
        print("Invalid owner details. Use a valid email, a nonblank name, and a password of 12–128 characters.")
    except ValueError as error:
        print(str(error))
    except SQLAlchemyError:
        print("Database operation failed. Check connectivity and apply migration 002_owner_auth.sql first.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
