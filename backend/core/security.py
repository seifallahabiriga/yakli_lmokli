from datetime import UTC, datetime, timedelta
from typing import Any

import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import get_settings
from backend.core.exceptions import TokenExpiredError, TokenInvalidError

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Password normalization (fix for bcrypt 72-byte limit)
# =============================================================================

def _normalize_password(password: str) -> str:
    """
    Converts any-length password into a fixed-length SHA-256 hex digest.
    This avoids bcrypt's 72-byte limitation while preserving determinism.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =============================================================================
# Password hashing
# =============================================================================

def hash_password(plain: str) -> str:
    return _pwd_context.hash(_normalize_password(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(_normalize_password(plain), hashed)


# =============================================================================
# JWT creation
# =============================================================================

def _build_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode(
        {**payload, "exp": expire, "iat": datetime.now(UTC)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_access_token(subject: int | str, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"sub": str(subject), "type": "access"}
    if extra:
        payload.update(extra)

    return _build_token(
        payload,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: int | str) -> str:
    return _build_token(
        {"sub": str(subject), "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# =============================================================================
# JWT verification
# =============================================================================

def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
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
    return _decode_token(token, "access")


def verify_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, "refresh")


def get_subject_from_token(token: str) -> str:
    payload = verify_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise TokenInvalidError()
    return sub


# =============================================================================
# Token pair
# =============================================================================

def create_token_pair(user_id: int, role: str) -> dict[str, str]:
    return {
        "access_token": create_access_token(
            subject=user_id,
            extra={"role": role},
        ),
        "refresh_token": create_refresh_token(subject=user_id),
        "token_type": "bearer",
    }