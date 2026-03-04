"""Authentication endpoints: register, login, refresh."""

from fastapi import APIRouter

from app.core.dependencies import DBSession
from app.generated.models import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: DBSession) -> TokenResponse:
    role = body.role.value if body.role else "USER"
    access, refresh = await auth_service.register(
        db,
        email=body.email,
        password=body.password,
        role=role,
    )
    return TokenResponse(access_token=access, refresh_token=refresh, token_type="bearer")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession) -> TokenResponse:
    access, refresh = await auth_service.login(db, email=body.email, password=body.password)
    return TokenResponse(access_token=access, refresh_token=refresh, token_type="bearer")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: DBSession) -> TokenResponse:
    access, refresh = await auth_service.refresh(db, body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=refresh, token_type="bearer")
