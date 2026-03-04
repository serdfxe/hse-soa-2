import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt as _bcrypt

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.exceptions import RefreshTokenInvalidError, TokenExpiredError, TokenInvalidError


# ── Passwords ─────────────────────────────────────────────────────────────────

def _prehash(plain: str) -> bytes:
    """SHA-256 → base64 so bcrypt always receives ≤44 bytes regardless of input length."""
    return base64.b64encode(hashlib.sha256(plain.encode()).digest())


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(_prehash(plain), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(_prehash(plain), hashed.encode())


# ── JWT Access Tokens ─────────────────────────────────────────────────────────

def create_access_token(user_id: UUID, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()

    if payload.get("type") != "access":
        raise TokenInvalidError()

    return payload


# ── Refresh Tokens ────────────────────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Store only the hash of the refresh token in the DB."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_token_pair(user_id: UUID, role: str) -> tuple[str, str]:
    """Return (access_token, refresh_token)."""
    access = create_access_token(user_id, role)
    refresh = generate_refresh_token()
    return access, refresh


# ── Refresh Token JWT (for encoding expiry info) ──────────────────────────────

def create_refresh_jwt(user_id: UUID, refresh_token_id: UUID) -> str:
    """Encode the refresh token as a signed JWT so the client can store one string."""
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(refresh_token_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_refresh_jwt(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except (ExpiredSignatureError, JWTError):
        raise RefreshTokenInvalidError()

    if payload.get("type") != "refresh":
        raise RefreshTokenInvalidError()

    return payload
