from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: SecretStr | None = None
    # Temporary, explicit single-business context for local development only.
    # Authentication should replace this with the caller's verified membership.
    dev_business_id: UUID | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
