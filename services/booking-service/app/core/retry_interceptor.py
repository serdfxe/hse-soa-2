"""Retry gRPC client interceptor with exponential backoff."""

import asyncio
import logging

import grpc
import grpc.aio

logger = logging.getLogger(__name__)

_RETRYABLE = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}
_NON_RETRYABLE = {grpc.StatusCode.INVALID_ARGUMENT, grpc.StatusCode.NOT_FOUND, grpc.StatusCode.RESOURCE_EXHAUSTED}


class RetryInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """
    Retries gRPC calls on UNAVAILABLE / DEADLINE_EXCEEDED with exponential backoff.
    Max 3 attempts: delays 100ms, 200ms, 400ms.
    No retry on INVALID_ARGUMENT, NOT_FOUND, RESOURCE_EXHAUSTED.
    """

    _DELAYS = [0.1, 0.2, 0.4]

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        last_error: grpc.aio.AioRpcError | None = None
        for attempt, delay in enumerate(self._DELAYS):
            if attempt > 0:
                logger.info("Retry attempt=%d method=%s delay=%.3f", attempt, client_call_details.method, delay)
                await asyncio.sleep(delay)
            try:
                return await continuation(client_call_details, request)
            except grpc.aio.AioRpcError as exc:
                if exc.code() in _NON_RETRYABLE:
                    raise
                if exc.code() in _RETRYABLE:
                    last_error = exc
                    continue
                raise
        assert last_error is not None
        raise last_error
