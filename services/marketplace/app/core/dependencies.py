from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccessDeniedError
from app.core.security import decode_access_token
from app.db.session import async_session_factory

_bearer_scheme = HTTPBearer(auto_error=False)


# ── Database Session ──────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── Current User ──────────────────────────────────────────────────────────────

class CurrentUser:
    """Lightweight current-user object extracted from JWT claims."""

    def __init__(self, user_id: UUID, role: str) -> None:
        self.user_id = user_id
        self.role = role


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> CurrentUser:
    from app.core.exceptions import TokenInvalidError

    if credentials is None:
        raise TokenInvalidError()

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = UUID(payload["sub"])
        role = payload["role"]
    except (KeyError, ValueError):
        raise TokenInvalidError()

    return CurrentUser(user_id=user_id, role=role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


# ── Role-Based Access Control ─────────────────────────────────────────────────

def require_role(*allowed_roles: str):
    """Dependency factory that enforces role-based access."""

    async def _check(user: AuthUser) -> CurrentUser:
        if user.role not in allowed_roles:
            raise AccessDeniedError()
        return user

    return Depends(_check)
