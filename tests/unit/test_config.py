"""Unit tests for ``app.core.config``."""

import pytest
from pydantic import ValidationError

from app._detail.constants import JWT_SECRET_MIN_LENGTH
from app.core.config import Settings

DB_URL = "sqlite+aiosqlite:///:memory:"


def test_short_jwt_secret_rejected_without_echoing_it() -> None:
    """A secret below the minimum fails and the error does not contain its value."""
    secret = "s" * (JWT_SECRET_MIN_LENGTH - 1)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=DB_URL, jwt_secret=secret)
    assert error.value.errors()[0]["loc"] == ("jwt_secret",)
    assert error.value.errors()[0]["type"] == "too_short"
    assert secret not in str(error.value)


def test_jwt_secret_of_minimum_length_accepted() -> None:
    """A secret of exactly the minimum length is accepted."""
    secret = "s" * JWT_SECRET_MIN_LENGTH
    settings = Settings(_env_file=None, database_url=DB_URL, jwt_secret=secret)
    assert settings.jwt_secret.get_secret_value() == secret
