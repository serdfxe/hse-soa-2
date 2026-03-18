"""Circuit Breaker gRPC client interceptor."""

import asyncio
import logging
import time
from enum import Enum

import grpc
import grpc.aio

from app.core.config import settings

logger = logging.getLogger(__name__)


class CBState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """
    Circuit Breaker as gRPC client interceptor.
    Parameters from environment via settings.
    Logs state transitions.
    """

    def __init__(self) -> None:
        self._state = CBState.CLOSED
        self._failure_count = 0
        self._open_until: float = 0.0
        self._lock = asyncio.Lock()
        self._failure_threshold = settings.cb_failure_threshold
        self._recovery_timeout = settings.cb_recovery_timeout

    @property
    def state(self) -> CBState:
        return self._state

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        async with self._lock:
            if self._state == CBState.OPEN:
                if time.monotonic() >= self._open_until:
                    self._state = CBState.HALF_OPEN
                    logger.info("Circuit Breaker: OPEN → HALF_OPEN")
                else:
                    raise grpc.aio.AioRpcError(
                        code=grpc.StatusCode.UNAVAILABLE,
                        initial_metadata=grpc.aio.Metadata(),
                        trailing_metadata=grpc.aio.Metadata(),
                        details="Circuit breaker is OPEN — service unavailable",
                    )

        try:
            response = await continuation(client_call_details, request)
            async with self._lock:
                if self._state == CBState.HALF_OPEN:
                    logger.info("Circuit Breaker: HALF_OPEN → CLOSED")
                    self._state = CBState.CLOSED
                self._failure_count = 0
            return response
        except grpc.aio.AioRpcError as exc:
            async with self._lock:
                if exc.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    prev = self._state
                    self._failure_count += 1
                    if self._state == CBState.HALF_OPEN or self._failure_count >= self._failure_threshold:
                        self._state = CBState.OPEN
                        self._open_until = time.monotonic() + self._recovery_timeout
                        logger.info("Circuit Breaker: %s → OPEN (failures=%d)", prev.value, self._failure_count)
            raise
