import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("marketplace.access")

_MUTABLE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SENSITIVE_FIELDS = frozenset({"password", "new_password", "old_password", "secret"})


def _mask_sensitive(data: Any, depth: int = 0) -> Any:
    """Recursively mask sensitive fields in request bodies."""
    if depth > 5:
        return data
    if isinstance(data, dict):
        return {
            k: "***" if k.lower() in _SENSITIVE_FIELDS else _mask_sensitive(v, depth + 1)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive(item, depth + 1) for item in data]
    return data


class JSONLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Read body for mutable requests (needed for logging; then reconstruct)
        body_data: dict | None = None
        if request.method in _MUTABLE_METHODS:
            raw_body = await request.body()
            if raw_body:
                try:
                    body_data = _mask_sensitive(json.loads(raw_body))
                except json.JSONDecodeError:
                    body_data = {"_raw": "<non-JSON body>"}
            # Starlette requires re-injecting the body so the route handler can read it
            async def receive():
                return {"type": "http.request", "body": raw_body, "more_body": False}

            request = Request(request.scope, receive)

        # Extract user_id from Authorization header if present
        user_id: str | None = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_access_token
                payload = decode_access_token(auth_header[7:])
                user_id = payload.get("sub")
            except Exception:
                pass

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_record: dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if body_data is not None:
            log_record["body"] = body_data

        logger.info(json.dumps(log_record))

        response.headers["X-Request-Id"] = request_id
        return response
