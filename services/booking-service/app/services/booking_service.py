"""Booking business logic."""

import logging
import uuid
from uuid import UUID

import grpc
import grpc.aio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BookingAlreadyCancelledError,
    BookingNotFoundError,
    FlightNotFoundError,
    FlightServiceUnavailableError,
    InsufficientSeatsError,
)
from app.core.grpc_client import _metadata, get_flight_stub
from app.db.models import Booking, BookingStatus
from app.generated import flight_pb2

logger = logging.getLogger(__name__)


async def search_flights(*, origin: str, destination: str, date: str) -> list[dict]:
    stub = get_flight_stub()
    try:
        response = await stub.SearchFlights(
            flight_pb2.SearchFlightsRequest(origin=origin, destination=destination, date=date),
            metadata=_metadata(),
        )
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            raise FlightServiceUnavailableError()
        raise
    return [_flight_proto_to_dict(f) for f in response.flights]


async def get_flight(flight_id: str) -> dict:
    stub = get_flight_stub()
    try:
        response = await stub.GetFlight(
            flight_pb2.GetFlightRequest(flight_id=flight_id),
            metadata=_metadata(),
        )
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise FlightNotFoundError(flight_id)
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            raise FlightServiceUnavailableError()
        raise
    return _flight_proto_to_dict(response.flight)


async def create_booking(
    db: AsyncSession,
    *,
    user_id: UUID,
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
    seat_count: int,
) -> Booking:
    stub = get_flight_stub()

    # 1. Get flight info (including price)
    try:
        flight_resp = await stub.GetFlight(
            flight_pb2.GetFlightRequest(flight_id=flight_id),
            metadata=_metadata(),
        )
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise FlightNotFoundError(flight_id)
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            raise FlightServiceUnavailableError()
        raise

    flight = flight_resp.flight
    booking_id = uuid.uuid4()
    total_price = round(seat_count * flight.price, 2)

    # 2. Reserve seats
    try:
        await stub.ReserveSeats(
            flight_pb2.ReserveSeatsRequest(
                flight_id=flight_id,
                seat_count=seat_count,
                booking_id=str(booking_id),
            ),
            metadata=_metadata(),
        )
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise InsufficientSeatsError()
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise FlightNotFoundError(flight_id)
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            raise FlightServiceUnavailableError()
        raise

    # 3. Create booking
    booking = Booking(
        id=booking_id,
        user_id=user_id,
        flight_id=UUID(flight_id),
        passenger_name=passenger_name,
        passenger_email=passenger_email,
        seat_count=seat_count,
        total_price=total_price,
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    await db.commit()
    return booking


async def get_booking(db: AsyncSession, booking_id: UUID) -> Booking:
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if booking is None:
        raise BookingNotFoundError()
    return booking


async def list_bookings(db: AsyncSession, user_id: UUID) -> list[Booking]:
    result = await db.execute(select(Booking).where(Booking.user_id == user_id))
    return list(result.scalars().all())


async def cancel_booking(db: AsyncSession, booking_id: UUID) -> Booking:
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if booking is None:
        raise BookingNotFoundError()
    if booking.status == BookingStatus.CANCELLED:
        raise BookingAlreadyCancelledError()

    # Release reservation in Flight Service
    stub = get_flight_stub()
    try:
        await stub.ReleaseReservation(
            flight_pb2.ReleaseReservationRequest(booking_id=str(booking_id)),
            metadata=_metadata(),
        )
    except grpc.aio.AioRpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            raise FlightServiceUnavailableError()
        # NOT_FOUND means reservation already released — proceed with cancellation
        if exc.code() != grpc.StatusCode.NOT_FOUND:
            raise

    booking.status = BookingStatus.CANCELLED
    await db.commit()
    return booking


def _flight_proto_to_dict(f) -> dict:
    status_map = {
        1: "SCHEDULED",
        2: "DEPARTED",
        3: "CANCELLED",
        4: "COMPLETED",
    }
    return {
        "id": f.id,
        "flight_number": f.flight_number,
        "airline": f.airline,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time.ToDatetime().isoformat(),
        "arrival_time": f.arrival_time.ToDatetime().isoformat(),
        "total_seats": f.total_seats,
        "available_seats": f.available_seats,
        "price": f.price,
        "status": status_map.get(f.status, "SCHEDULED"),
    }
