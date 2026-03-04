"""FastAPI application factory and entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api import auth, orders, products, promo_codes
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, request_validation_error_handler
from app.core.logging_middleware import JSONLoggingMiddleware

# ── Logging setup ─────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_logging()

# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Middleware (order matters: outermost first)
app.add_middleware(JSONLoggingMiddleware)

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(ValidationError, request_validation_error_handler)

# Routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(promo_codes.router)


@app.get("/health", tags=["System"], include_in_schema=True)
async def health() -> dict:
    return {"status": "ok"}
