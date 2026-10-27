"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Attributes
    ----------
    database_url : str
        Async SQLAlchemy URL (``postgresql+asyncpg://...``).
    jwt_secret : SecretStr
        Key used to sign access tokens.
    jwt_algorithm : str
        JWT signing algorithm.
    jwt_expire_minutes : int
        Access token lifetime in minutes.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    jwt_secret: SecretStr
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
