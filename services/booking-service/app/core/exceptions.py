from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class AppError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int, details: dict[str, Any] | None = None) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error_code": self.error_code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


class FlightNotFoundError(AppError):
    def __init__(self, flight_id: Any = None) -> None:
        super().__init__(
            error_code="FLIGHT_NOT_FOUND",
            message=f"Flight '{flight_id}' not found" if flight_id else "Flight not found",
            status_code=404,
        )


class BookingNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(error_code="BOOKING_NOT_FOUND", message="Booking not found", status_code=404)


class InsufficientSeatsError(AppError):
    def __init__(self) -> None:
        super().__init__(error_code="INSUFFICIENT_SEATS", message="Not enough available seats", status_code=409)


class BookingAlreadyCancelledError(AppError):
    def __init__(self) -> None:
        super().__init__(error_code="BOOKING_ALREADY_CANCELLED", message="Booking is already cancelled", status_code=409)


class FlightServiceUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="FLIGHT_SERVICE_UNAVAILABLE",
            message="Flight service is temporarily unavailable. Please try again later.",
            status_code=503,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def request_validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from fastapi.exceptions import RequestValidationError
    assert isinstance(exc, RequestValidationError)
    fields = []
    for err in exc.errors():
        loc_parts = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        fields.append({"field": ".".join(loc_parts) or str(err["loc"][-1]), "message": err["msg"]})
    return JSONResponse(
        status_code=400,
        content={"error_code": "VALIDATION_ERROR", "message": "Validation failed", "details": {"fields": fields}},
    )
