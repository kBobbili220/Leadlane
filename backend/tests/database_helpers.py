from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.core.security import password_hasher
from backend.app.models import AuthRateLimit, AuthSession, BusinessMembership, User
from backend.app.services.auth import issue_session

TEST_PASSWORD = "Correct horse battery staple 42"
FIXTURE_HASH = password_hasher.hash(TEST_PASSWORD)


def sqlite_database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def functions(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("gen_random_uuid", 0, lambda: uuid4().hex)
        connection.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())
        connection.create_function("btrim", 1, lambda value: value.strip(" ") if value is not None else None)
        connection.create_function("octet_length", 1, lambda value: len(value) if value is not None else None)

    with engine.begin() as connection:
        # PostgreSQL JSONB and its regex checks are covered by DDL parity/live PG
        # tests. SQLite supplies a compatible business table for HTTP tests.
        connection.exec_driver_sql("""CREATE TABLE businesses (
            id UUID PRIMARY KEY DEFAULT (gen_random_uuid()),
            slug VARCHAR(100) NOT NULL UNIQUE, name VARCHAR(200) NOT NULL,
            email VARCHAR(254), phone VARCHAR(32), timezone VARCHAR(100) NOT NULL DEFAULT 'UTC',
            currency VARCHAR(3) NOT NULL DEFAULT 'USD', address JSON NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at DATETIME NOT NULL DEFAULT (now()), updated_at DATETIME NOT NULL DEFAULT (now())
        )""")
        for model in (User, BusinessMembership, AuthSession, AuthRateLimit):
            model.__table__.create(connection)
    return engine


def fixture_owner(session, business, email=None):
    user = User(full_name="Test owner", email=email or f"owner-{uuid4()}@example.com", password_hash=FIXTURE_HASH)
    session.add(user)
    session.flush()
    membership = BusinessMembership(user_id=user.id, business_id=business.id)
    session.add(membership)
    session.flush()
    response = issue_session(session, user, membership, business, Settings(_env_file=None))
    session.commit()
    return response
