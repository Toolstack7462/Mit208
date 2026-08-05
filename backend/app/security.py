"""Password hashing (bcrypt) and JWT token helpers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt

from .config import settings

# bcrypt hashes at most 72 bytes of input and raises ValueError beyond that.
# Anything longer must be rejected explicitly rather than silently truncated:
# truncating would make "<72 identical bytes>abc" and "<same 72 bytes>xyz"
# interchangeable passwords.
BCRYPT_MAX_BYTES = 72

# Marks this token as an API access token. Validated on decode so a token minted
# for some other purpose later (e.g. a refresh or password-reset token) cannot be
# replayed against the API.
TOKEN_TYPE_ACCESS = "access"


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can hash."""


def _password_bytes(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise PasswordTooLongError(
            f"Password must be {BCRYPT_MAX_BYTES} bytes or fewer "
            f"(received {len(encoded)}). Note that accented and non-Latin "
            "characters use more than one byte each."
        )
    return encoded


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True only for a matching password. Never raises."""
    try:
        return bcrypt.checkpw(_password_bytes(plain), hashed.encode("utf-8"))
    except (PasswordTooLongError, ValueError, TypeError):
        # An over-long or malformed input simply does not match any stored hash.
        return False


# Pre-computed hash of a value no account uses. Verifying against it costs the
# same as a real check, which keeps "unknown email" and "wrong password" close
# enough in duration that response time does not disclose which addresses exist.
_DUMMY_HASH = bcrypt.hashpw(b"phishguard-timing-equaliser", bcrypt.gensalt()).decode("utf-8")


def dummy_verify(plain: str) -> None:
    """Burn one bcrypt comparison. Result is intentionally discarded."""
    verify_password(plain, _DUMMY_HASH)


def create_access_token(subject: str, role: str) -> str:
    """Mint a signed access token.

    ``role`` is carried for display only — every authorisation decision re-reads
    the role from the database (see ``deps.get_current_user``), so a tampered
    claim grants nothing.

    ``jti`` and ``iat`` are included so an individual token can be identified in
    a log and so its age is verifiable; they are what a future revocation list
    would key on.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "typ": TOKEN_TYPE_ACCESS,
        "iat": now,
        "jti": uuid4().hex,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token.

    Raises ``jwt.PyJWTError`` on any invalid, expired or wrong-type token. The
    algorithm allow-list is explicit, so a token claiming ``alg: none`` or a
    different algorithm is rejected rather than trusted.
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["exp", "sub"]},
    )
    if payload.get("typ") != TOKEN_TYPE_ACCESS:
        raise jwt.InvalidTokenError("Token is not an access token")
    return payload
