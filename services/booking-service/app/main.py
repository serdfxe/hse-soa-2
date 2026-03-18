"""FastAPI application factory."""

import logging
import sys

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api import bookings, flights
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, request_validation_error_handler


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


_configure_logging()

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)

app.include_router(flights.router)
app.include_router(bookings.router)


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {"status": "ok"}
