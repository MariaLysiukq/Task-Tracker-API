"""Unit tests for ``app.core.security``."""

from datetime import timedelta

import jwt
import pytest

from app._detail.helpers import utc_now
from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_salted_and_verifiable() -> None:
    """Hashes differ per call, verify the right password and reject a wrong one."""
    first = hash_password("correct-horse")
    assert first != "correct-horse"
    assert first != hash_password("correct-horse")
    assert verify_password("correct-horse", first)
    assert not verify_password("wrong-horse", first)


def test_verify_without_hash_is_false() -> None:
    """An unknown user (no hash) never verifies."""
    assert not verify_password("anything", None)


def test_token_round_trip(settings: Settings) -> None:
    """A fresh token decodes to its subject."""
    assert decode_access_token(create_access_token(42)) == 42


def test_token_expires_after_configured_minutes(settings: Settings) -> None:
    """``exp`` equals ``iat`` plus ``JWT_EXPIRE_MINUTES``."""
    payload = jwt.decode(
        create_access_token(1),
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["exp"] - payload["iat"] == settings.jwt_expire_minutes * 60


def make_token(settings: Settings, payload: dict[str, object], key: str | None = None) -> str:
    """Encode an arbitrary payload.

    Parameters
    ----------
    settings : Settings
        Test settings.
    payload : dict[str, object]
        Claims to encode.
    key : str | None
        Signing key; defaults to the configured secret.

    Returns
    -------
    str
        Encoded JWT.
    """
    secret = key or settings.jwt_secret.get_secret_value()
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


@pytest.mark.parametrize(
    ("payload", "key"),
    [
        ({"sub": "1", "exp": utc_now() - timedelta(seconds=1)}, None),
        ({"sub": "1", "exp": utc_now() + timedelta(minutes=5)}, "other-secret"),
        ({"exp": utc_now() + timedelta(minutes=5)}, None),
        ({"sub": "1"}, None),
        ({"sub": "abc", "exp": utc_now() + timedelta(minutes=5)}, None),
    ],
    ids=["expired", "bad-signature", "no-sub", "no-exp", "non-numeric-sub"],
)
def test_invalid_tokens_rejected(
    settings: Settings,
    payload: dict[str, object],
    key: str | None,
) -> None:
    """Expired, foreign, incomplete and malformed tokens raise 401."""
    with pytest.raises(UnauthorizedError):
        decode_access_token(make_token(settings, payload, key))


def test_garbage_token_rejected(settings: Settings) -> None:
    """A non-JWT string raises 401."""
    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-token")
