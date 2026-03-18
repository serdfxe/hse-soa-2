"""gRPC client for Flight Service."""

import grpc
import grpc.aio

from app.core.circuit_breaker import CircuitBreakerInterceptor
from app.core.config import settings
from app.core.retry_interceptor import RetryInterceptor
from app.generated import flight_pb2_grpc

_circuit_breaker = CircuitBreakerInterceptor()
_retry = RetryInterceptor()

_channel: grpc.aio.Channel | None = None


def get_channel() -> grpc.aio.Channel:
    global _channel
    if _channel is None:
        _channel = grpc.aio.insecure_channel(
            settings.flight_service_url,
            interceptors=[_circuit_breaker, _retry],
        )
    return _channel


def get_flight_stub() -> flight_pb2_grpc.FlightServiceStub:
    return flight_pb2_grpc.FlightServiceStub(get_channel())


def _metadata() -> tuple:
    return (("x-api-key", settings.grpc_api_key),)
