from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_settings
from core.exceptions import TokenExpiredError, TokenInvalidError

settings = get_settings()

# =============================================================================
# Password hashing
# =============================================================================

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Returns a bcrypt hash of the given plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Returns True if the plaintext matches the stored hash."""
    return _pwd_context.verify(plain, hashed)


# =============================================================================
# JWT — token creation
# =============================================================================

def _build_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    """Internal helper — encodes a JWT with an expiry claim."""
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode(
        {**payload, "exp": expire, "iat": datetime.now(UTC)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_access_token(subject: int | str, extra: dict[str, Any] | None = None) -> str:
    """
    Creates a short-lived access token.

    Args:
        subject:  User ID (stored as the 'sub' claim).
        extra:    Optional additional claims (e.g. {"role": "admin"}).

    Returns:
        Encoded JWT string.
    """
    payload: dict[str, Any] = {"sub": str(subject), "type": "access"}
    if extra:
        payload.update(extra)
    return _build_token(
        payload,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: int | str) -> str:
    """
    Creates a long-lived refresh token.

    Refresh tokens carry only the subject claim — no role or extra data.
    They are exchanged for a new access token at /auth/refresh.
    """
    return _build_token(
        {"sub": str(subject), "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# =============================================================================
# JWT — token verification
# =============================================================================

def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """
    Internal helper — decodes and validates a JWT.

    Raises:
        TokenExpiredError:  Token is past its 'exp' claim.
        TokenInvalidError:  Token is malformed, tampered, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        if "expired" in str(exc).lower():
            raise TokenExpiredError() from exc
        raise TokenInvalidError() from exc

    if payload.get("type") != expected_type:
        raise TokenInvalidError()

    return payload


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Verifies an access token and returns its payload.

    Returns:
        Decoded payload dict (includes 'sub', 'type', 'exp', 'iat', and any extras).

    Raises:
        TokenExpiredError | TokenInvalidError
    """
    return _decode_token(token, expected_type="access")


def verify_refresh_token(token: str) -> dict[str, Any]:
    """
    Verifies a refresh token and returns its payload.

    Raises:
        TokenExpiredError | TokenInvalidError
    """
    return _decode_token(token, expected_type="refresh")


def get_subject_from_token(token: str) -> str:
    """
    Convenience helper — extracts only the 'sub' claim from an access token.

    Useful when you only need the user ID and don't care about other claims.
    """
    payload = verify_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise TokenInvalidError()
    return sub


# =============================================================================
# Token pair helper
# =============================================================================

def create_token_pair(
    user_id: int,
    role: str,
) -> dict[str, str]:
    """
    Creates an access + refresh token pair in one call.

    Used at login and at /auth/refresh.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "token_type": "bearer",
        }
    """
    return {
        "access_token": create_access_token(
            subject=user_id,
            extra={"role": role},
        ),
        "refresh_token": create_refresh_token(subject=user_id),
        "token_type": "bearer",
    }