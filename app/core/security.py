"""Password hashing and JWT access tokens."""

from datetime import timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash

from app._detail.helpers import utc_now
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

INVALID_TOKEN = "Invalid or expired token"  # noqa: S105 - error message, not a secret
_password_hash = PasswordHash.recommended()


@lru_cache
def _dummy_hash() -> str:
    """Return a hash used to equalize login timing for unknown emails.

    Returns
    -------
    str
        Argon2 hash of a fixed value.
    """
    return _password_hash.hash("timing-equalizer")


def hash_password(password: str) -> str:
    """Hash a plain password with Argon2.

    Parameters
    ----------
    password : str
        Plain password.

    Returns
    -------
    str
        Salted hash safe to store.
    """
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    """Check a password against a stored hash.

    Parameters
    ----------
    password : str
        Plain password.
    hashed_password : str | None
        Stored hash; ``None`` (unknown user) still runs a full verification
        so response time does not reveal registered emails.

    Returns
    -------
    bool
        ``True`` only if ``hashed_password`` is set and matches.
    """
    if hashed_password is None:
        _password_hash.verify(password, _dummy_hash())
        return False
    return _password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    """Issue a signed access token for a user.

    Parameters
    ----------
    user_id : int
        Token subject.

    Returns
    -------
    str
        Encoded JWT with ``sub``, ``iat`` and ``exp`` claims.
    """
    settings = get_settings()
    issued_at = utc_now()
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int:
    """Validate an access token and return its subject.

    Parameters
    ----------
    token : str
        Encoded JWT.

    Returns
    -------
    int
        User identifier from the ``sub`` claim.

    Raises
    ------
    UnauthorizedError
        If the token is malformed, badly signed, expired or lacks a numeric ``sub``.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError) as error:
        raise UnauthorizedError(INVALID_TOKEN) from error
