"""Flight business logic."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Flight, FlightStatus, ReservationStatus, SeatReservation
from app.services import cache_service

logger = logging.getLogger(__name__)


def _flight_cache_key(flight_id: str) -> str:
    return f"flight:{flight_id}"


def _search_cache_key(origin: str, destination: str, date: str) -> str:
    return f"search:{origin}:{destination}:{date}"


def _flight_to_dict(f: Flight) -> dict:
    return {
        "id": str(f.id),
        "flight_number": f.flight_number,
        "airline": f.airline,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time.isoformat(),
        "arrival_time": f.arrival_time.isoformat(),
        "total_seats": f.total_seats,
        "available_seats": f.available_seats,
        "price": float(f.price),
        "status": f.status.value,
    }


async def search_flights(
    db: AsyncSession, *, origin: str, destination: str, date: str
) -> list[Flight]:
    cache_key = _search_cache_key(origin, destination, date)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        # Return as list of dicts - the servicer will convert
        return cached

    query = (
        select(Flight)
        .where(
            Flight.origin == origin.upper(),
            Flight.destination == destination.upper(),
            Flight.status == FlightStatus.SCHEDULED,
        )
    )
    if date:
        query = query.where(Flight.departure_date == date)

    result = await db.execute(query)
    flights = list(result.scalars().all())

    flight_dicts = [_flight_to_dict(f) for f in flights]
    await cache_service.set(cache_key, flight_dicts)
    return flight_dicts


async def get_flight(db: AsyncSession, flight_id: str) -> dict | None:
    cache_key = _flight_cache_key(flight_id)
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return cached

    try:
        fid = uuid.UUID(flight_id)
    except ValueError:
        return None

    result = await db.execute(select(Flight).where(Flight.id == fid))
    flight = result.scalar_one_or_none()
    if flight is None:
        return None

    data = _flight_to_dict(flight)
    await cache_service.set(cache_key, data)
    return data


async def reserve_seats(
    db: AsyncSession, *, flight_id: str, seat_count: int, booking_id: str
) -> str:
    """
    Atomically reserve seats. Idempotent: if booking_id already has an ACTIVE reservation,
    return its id. Uses SELECT FOR UPDATE to prevent race conditions.
    """
    try:
        fid = uuid.UUID(flight_id)
        bid = uuid.UUID(booking_id)
    except ValueError:
        raise ValueError("Invalid UUID")

    # Idempotency check
    existing = await db.execute(
        select(SeatReservation).where(
            SeatReservation.booking_id == bid,
            SeatReservation.status == ReservationStatus.ACTIVE,
        )
    )
    existing_res = existing.scalar_one_or_none()
    if existing_res is not None:
        logger.info("Idempotent reserve_seats booking_id=%s existing=%s", booking_id, existing_res.id)
        return str(existing_res.id)

    # Lock the flight row
    flight_result = await db.execute(
        select(Flight).where(Flight.id == fid).with_for_update()
    )
    flight = flight_result.scalar_one_or_none()
    if flight is None:
        raise LookupError("Flight not found")

    if flight.available_seats < seat_count:
        raise ResourceError(f"Not enough seats: available={flight.available_seats}, requested={seat_count}")

    flight.available_seats -= seat_count

    reservation = SeatReservation(
        flight_id=fid,
        booking_id=bid,
        seat_count=seat_count,
        status=ReservationStatus.ACTIVE,
    )
    db.add(reservation)
    await db.commit()

    # Invalidate cache
    await cache_service.delete(_flight_cache_key(flight_id))

    return str(reservation.id)


async def release_reservation(db: AsyncSession, *, booking_id: str) -> bool:
    try:
        bid = uuid.UUID(booking_id)
    except ValueError:
        raise ValueError("Invalid UUID")

    result = await db.execute(
        select(SeatReservation)
        .where(
            SeatReservation.booking_id == bid,
            SeatReservation.status == ReservationStatus.ACTIVE,
        )
        .with_for_update()
    )
    reservation = result.scalar_one_or_none()
    if reservation is None:
        raise LookupError("Active reservation not found")

    # Return seats to flight
    flight_result = await db.execute(
        select(Flight).where(Flight.id == reservation.flight_id).with_for_update()
    )
    flight = flight_result.scalar_one_or_none()
    if flight:
        flight.available_seats += reservation.seat_count

    reservation.status = ReservationStatus.RELEASED
    await db.commit()

    if flight:
        await cache_service.delete(_flight_cache_key(str(reservation.flight_id)))

    return True


class ResourceError(Exception):
    pass
