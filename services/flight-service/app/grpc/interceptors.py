"""gRPC server interceptors."""

import logging

import grpc
import grpc.aio

from app.core.config import settings

logger = logging.getLogger(__name__)


class ApiKeyInterceptor(grpc.aio.ServerInterceptor):
    """Validates x-api-key metadata on every incoming call."""

    async def intercept_service(
        self,
        continuation,
        handler_call_details: grpc.HandlerCallDetails,
    ):
        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get("x-api-key", "")
        if api_key != settings.grpc_api_key:
            logger.warning("Rejected unauthenticated call method=%s", handler_call_details.method)

            async def _unauthenticated(request, context: grpc.aio.ServicerContext):
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")

            return grpc.unary_unary_rpc_method_handler(_unauthenticated)

        return await continuation(handler_call_details)
