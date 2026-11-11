"""Run with: python -m backend.app.db.check_connection

Uses the application's settings and driver, without printing credentials.
"""

from urllib.parse import quote, quote_plus

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import PROJECT_ROOT, get_settings
from backend.app.db.session import get_engine


def redact_error(message: str, database_url: str, password: str | None) -> str:
    secrets = [database_url]
    if password:
        secrets.extend((password, quote(password, safe=""), quote_plus(password, safe="")))
    for secret in sorted(set(secrets), key=len, reverse=True):
        message = message.replace(secret, "[redacted]")
    return message


def main() -> int:
    print(f"Settings file: {PROJECT_ROOT / '.env'}")
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuration invalid. Check DATABASE_URL and DEV_BUSINESS_ID in your environment/.env.")
        return 1
    if settings.database_url is None:
        print("DATABASE_URL is missing.")
        return 1
    database_url = settings.database_url.get_secret_value()
    password = None
    engine = None
    try:
        url = make_url(database_url)
        password = url.password
        # Bound the diagnostic wait while retaining the application's credentials.
        diagnostic_url = url.update_query_dict({"connect_timeout": "5"})
        engine = get_engine(diagnostic_url.render_as_string(hide_password=False))
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            print("Database connection: OK")
            tables = connection.execute(text(
                "SELECT to_regclass('businesses'), to_regclass('services')"
            )).one()
            if any(table is None for table in tables):
                print("Required tables are missing from the connection's search path. Apply the SQL migration to this database.")
                return 1
            print("Required tables: OK")
            if settings.dev_business_id is None:
                print("DEV_BUSINESS_ID is missing.")
                return 1
            active = connection.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM businesses WHERE id = :id AND is_active = true)"
            ), {"id": settings.dev_business_id})
            if not active:
                print("DEV_BUSINESS_ID does not identify an active business in this database.")
                return 1
            print("Business context: OK")
            print("All checks passed. Restart FastAPI using this same virtual environment and configuration.")
            return 0
    except (SQLAlchemyError, ValueError, ImportError) as exc:
        original = getattr(exc, "orig", exc)
        print("Database check failed:")
        print(redact_error(str(original), database_url, password))
        print("If the password contains URL-reserved characters, percent-encode it in DATABASE_URL.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()
        get_engine.cache_clear()


if __name__ == "__main__":
    raise SystemExit(main())
