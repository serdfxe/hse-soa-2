"""gRPC FlightService servicer."""

import logging
from datetime import datetime, timezone

import grpc
import grpc.aio
from google.protobuf.timestamp_pb2 import Timestamp

from app.db.session import async_session_factory
from app.generated import flight_pb2, flight_pb2_grpc
from app.services import flight_service
from app.services.flight_service import ResourceError

logger = logging.getLogger(__name__)


def _ts(dt_str: str) -> Timestamp:
    """Convert ISO datetime string to protobuf Timestamp."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


def _dict_to_flight(d: dict) -> flight_pb2.Flight:
    status_map = {
        "SCHEDULED": flight_pb2.SCHEDULED,
        "DEPARTED": flight_pb2.DEPARTED,
        "CANCELLED": flight_pb2.CANCELLED,
        "COMPLETED": flight_pb2.COMPLETED,
    }
    return flight_pb2.Flight(
        id=d["id"],
        flight_number=d["flight_number"],
        airline=d["airline"],
        origin=d["origin"],
        destination=d["destination"],
        departure_time=_ts(d["departure_time"]),
        arrival_time=_ts(d["arrival_time"]),
        total_seats=d["total_seats"],
        available_seats=d["available_seats"],
        price=d["price"],
        status=status_map.get(d["status"], flight_pb2.SCHEDULED),
    )


class FlightServiceServicer(flight_pb2_grpc.FlightServiceServicer):

    async def SearchFlights(self, request, context: grpc.aio.ServicerContext):
        async with async_session_factory() as db:
            flights = await flight_service.search_flights(
                db,
                origin=request.origin,
                destination=request.destination,
                date=request.date,
            )
        return flight_pb2.SearchFlightsResponse(
            flights=[_dict_to_flight(f) for f in flights]
        )

    async def GetFlight(self, request, context: grpc.aio.ServicerContext):
        async with async_session_factory() as db:
            flight = await flight_service.get_flight(db, request.flight_id)
        if flight is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"Flight '{request.flight_id}' not found")
        return flight_pb2.GetFlightResponse(flight=_dict_to_flight(flight))

    async def ReserveSeats(self, request, context: grpc.aio.ServicerContext):
        async with async_session_factory() as db:
            try:
                reservation_id = await flight_service.reserve_seats(
                    db,
                    flight_id=request.flight_id,
                    seat_count=request.seat_count,
                    booking_id=request.booking_id,
                )
            except LookupError as exc:
                await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
            except ResourceError as exc:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return flight_pb2.ReserveSeatsResponse(reservation_id=reservation_id)

    async def ReleaseReservation(self, request, context: grpc.aio.ServicerContext):
        async with async_session_factory() as db:
            try:
                success = await flight_service.release_reservation(
                    db, booking_id=request.booking_id
                )
            except LookupError as exc:
                await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return flight_pb2.ReleaseReservationResponse(success=success)
