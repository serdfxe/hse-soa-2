"""Authentication and token management service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    RefreshTokenInvalidError,
)
from app.core.security import (
    create_access_token,
    create_refresh_jwt,
    decode_refresh_jwt,
    hash_password,
    hash_refresh_token,
    generate_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, Role, User


async def register(
    db: AsyncSession,
    email: str,
    password: str,
    role: str = "USER",
) -> tuple[str, str]:
    """Create a new user and return (access_token, refresh_token)."""
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        role=Role(role),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise EmailAlreadyExistsError()

    access_token, refresh_jwt = await _issue_token_pair(db, user)
    await db.commit()
    return access_token, refresh_jwt


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[str, str]:
    """Authenticate user and return (access_token, refresh_token)."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    access_token, refresh_jwt = await _issue_token_pair(db, user)
    await db.commit()
    return access_token, refresh_jwt


async def refresh(
    db: AsyncSession,
    refresh_jwt: str,
) -> tuple[str, str]:
    """Validate refresh JWT, rotate token, and return new pair."""
    payload = decode_refresh_jwt(refresh_jwt)

    try:
        user_id = UUID(payload["sub"])
        token_record_id = UUID(payload["jti"])
    except (KeyError, ValueError):
        raise RefreshTokenInvalidError()

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.id == token_record_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    token_record = result.scalar_one_or_none()
    if token_record is None:
        raise RefreshTokenInvalidError()

    # Revoke the old token (rotation)
    token_record.revoked = True

    # Load user for role claim
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise RefreshTokenInvalidError()

    access_token, new_refresh_jwt = await _issue_token_pair(db, user)
    await db.commit()
    return access_token, new_refresh_jwt


# ── Internal ──────────────────────────────────────────────────────────────────

async def _issue_token_pair(db: AsyncSession, user: User) -> tuple[str, str]:
    """Create access token and a persisted refresh token; return both as strings."""
    raw_refresh = generate_refresh_token()

    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.flush()  # populate token_record.id

    # Encode as JWT so the client only needs to store one opaque string
    refresh_jwt = create_refresh_jwt(user.id, token_record.id)
    access_token = create_access_token(user.id, user.role.value)

    return access_token, refresh_jwt
