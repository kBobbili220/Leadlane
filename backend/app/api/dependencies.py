from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_session
from backend.app.models import Business

DatabaseSession = Annotated[Session, Depends(get_session)]


def get_current_business_id(
    session: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    """Development context; replace this dependency when authentication is added."""
    if settings.dev_business_id is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Business context is not configured")
    business_id = session.scalar(
        select(Business.id).where(Business.id == settings.dev_business_id, Business.is_active.is_(True))
    )
    if business_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business_id


CurrentBusinessID = Annotated[UUID, Depends(get_current_business_id)]
