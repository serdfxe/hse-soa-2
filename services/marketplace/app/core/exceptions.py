from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class AppError(Exception):
    """Base class for all application business errors."""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


# ── Catalogue ─────────────────────────────────────────────────────────────────

class ProductNotFoundError(AppError):
    def __init__(self, product_id: Any = None) -> None:
        super().__init__(
            error_code="PRODUCT_NOT_FOUND",
            message="Product not found" if product_id is None else f"Product '{product_id}' not found",
            status_code=404,
        )


class ProductInactiveError(AppError):
    def __init__(self, product_id: Any = None) -> None:
        super().__init__(
            error_code="PRODUCT_INACTIVE",
            message="Product is not active and cannot be ordered",
            status_code=409,
            details={"product_id": str(product_id)} if product_id else None,
        )


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="ORDER_NOT_FOUND",
            message="Order not found",
            status_code=404,
        )


class OrderLimitExceededError(AppError):
    def __init__(self, wait_minutes: int) -> None:
        super().__init__(
            error_code="ORDER_LIMIT_EXCEEDED",
            message=f"Please wait {wait_minutes} minute(s) before creating or updating an order",
            status_code=429,
            details={"wait_minutes": wait_minutes},
        )


class OrderHasActiveError(AppError):
    def __init__(self, active_order_id: Any = None) -> None:
        super().__init__(
            error_code="ORDER_HAS_ACTIVE",
            message="You already have an active order (CREATED or PAYMENT_PENDING)",
            status_code=409,
            details={"active_order_id": str(active_order_id)} if active_order_id else None,
        )


class InvalidStateTransitionError(AppError):
    def __init__(self, current: str, target: str | None = None) -> None:
        msg = f"Cannot transition order from state '{current}'"
        if target:
            msg += f" to '{target}'"
        super().__init__(
            error_code="INVALID_STATE_TRANSITION",
            message=msg,
            status_code=409,
            details={"current_status": current, "target_status": target},
        )


class InsufficientStockError(AppError):
    def __init__(self, shortages: list[dict[str, Any]]) -> None:
        super().__init__(
            error_code="INSUFFICIENT_STOCK",
            message="One or more products do not have sufficient stock",
            status_code=409,
            details={"shortages": shortages},
        )


class OrderOwnershipViolationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="ORDER_OWNERSHIP_VIOLATION",
            message="This order belongs to another user",
            status_code=403,
        )


# ── Promo Codes ───────────────────────────────────────────────────────────────

class PromoCodeInvalidError(AppError):
    def __init__(self, reason: str = "Promo code is invalid, expired, or exhausted") -> None:
        super().__init__(
            error_code="PROMO_CODE_INVALID",
            message=reason,
            status_code=422,
        )


class PromoCodeMinAmountError(AppError):
    def __init__(self, min_amount: float, actual_amount: float) -> None:
        super().__init__(
            error_code="PROMO_CODE_MIN_AMOUNT",
            message="Order total is below the minimum required for this promo code",
            status_code=422,
            details={"min_order_amount": min_amount, "order_total": actual_amount},
        )


class PromoCodeAlreadyExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="PROMO_CODE_ALREADY_EXISTS",
            message="A promo code with this code already exists",
            status_code=409,
        )


# ── Auth ──────────────────────────────────────────────────────────────────────

class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )


class EmailAlreadyExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="EMAIL_ALREADY_EXISTS",
            message="An account with this email already exists",
            status_code=409,
        )


class TokenExpiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="TOKEN_EXPIRED",
            message="Access token has expired",
            status_code=401,
        )


class TokenInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="TOKEN_INVALID",
            message="Access token is invalid",
            status_code=401,
        )


class RefreshTokenInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="REFRESH_TOKEN_INVALID",
            message="Refresh token is invalid or expired",
            status_code=401,
        )


class AccessDeniedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="ACCESS_DENIED",
            message="You do not have permission to perform this action",
            status_code=403,
        )


# ── Exception Handlers ────────────────────────────────────────────────────────

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    fields = [
        {"field": ".".join(str(loc) for loc in err["loc"] if loc != "body"), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": {"fields": fields},
        },
    )


async def request_validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from fastapi.exceptions import RequestValidationError

    assert isinstance(exc, RequestValidationError)
    fields = []
    for err in exc.errors():
        loc_parts = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        fields.append({"field": ".".join(loc_parts) or err["loc"][-1], "message": err["msg"]})
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": {"fields": fields},
        },
    )
