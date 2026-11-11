from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.services.auth import OwnerContext, authenticate, unauthorized

DatabaseSession = Annotated[Session, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


def get_bearer_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    # This dependency runs before opening a DB session, including missing headers.
    if credentials is None or credentials.scheme.lower() != "bearer" or not 1 <= len(credentials.credentials) <= 512:
        raise unauthorized()
    return credentials.credentials


BearerToken = Annotated[str, Depends(get_bearer_token)]


def get_current_owner(token: BearerToken, session: DatabaseSession) -> OwnerContext:
    return authenticate(session, token)


CurrentOwner = Annotated[OwnerContext, Depends(get_current_owner)]


def get_current_business_id(owner: CurrentOwner) -> UUID:
    return owner.business.id


CurrentBusinessID = Annotated[UUID, Depends(get_current_business_id)]
