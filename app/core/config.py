"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app._detail.constants import JWT_SECRET_MIN_LENGTH


class Settings(BaseSettings):
    """Runtime configuration.

    Validation errors never include the submitted values, so a rejected
    secret does not end up in logs.

    Attributes
    ----------
    database_url : str
        Async SQLAlchemy URL (``postgresql+asyncpg://...``).
    jwt_secret : SecretStr
        Key used to sign access tokens; at least ``JWT_SECRET_MIN_LENGTH`` characters.
    jwt_algorithm : str
        JWT signing algorithm.
    jwt_expire_minutes : int
        Access token lifetime in minutes.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: str
    jwt_secret: SecretStr = Field(min_length=JWT_SECRET_MIN_LENGTH)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Returns
    -------
    Settings
        Settings instance built from the environment.
    """
    return Settings()
