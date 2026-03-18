"""Flight Service gRPC server entry point."""

import asyncio
import logging
import sys

import grpc
import grpc.aio

from app.core.config import settings
from app.generated import flight_pb2_grpc
from app.grpc.interceptors import ApiKeyInterceptor
from app.grpc.servicer import FlightServiceServicer


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


async def serve() -> None:
    _configure_logging()
    server = grpc.aio.server(interceptors=[ApiKeyInterceptor()])
    flight_pb2_grpc.add_FlightServiceServicer_to_server(FlightServiceServicer(), server)
    listen_addr = f"0.0.0.0:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    logging.getLogger(__name__).info("Flight gRPC server starting on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
