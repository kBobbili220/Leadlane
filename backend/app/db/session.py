from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, InterfaceError, OperationalError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.drivername.split("+")[0] not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL must use PostgreSQL")
    return create_engine(
        url.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        hide_parameters=True,
    )


def get_session(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    if settings.database_url is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    try:
        engine = get_engine(settings.database_url.get_secret_value())
    except (ArgumentError, ValueError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database configuration is invalid") from None
    try:
        # Each request owns its session. Writes commit explicitly; close rolls
        # back unfinished transactions, including requests that raised an error.
        with Session(engine, expire_on_commit=False) as session:
            yield session
    except (InterfaceError, OperationalError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is unavailable") from None
