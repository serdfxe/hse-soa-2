"""Booking management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, EmailStr

from app.core.dependencies import DBSession
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["Bookings"])


class BookingCreate(BaseModel):
    user_id: UUID
    flight_id: str
    passenger_name: str
    passenger_email: EmailStr
    seat_count: int


class BookingResponse(BaseModel):
    id: UUID
    user_id: UUID
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking(body: BookingCreate, db: DBSession) -> BookingResponse:
    booking = await booking_service.create_booking(
        db,
        user_id=body.user_id,
        flight_id=body.flight_id,
        passenger_name=body.passenger_name,
        passenger_email=body.passenger_email,
        seat_count=body.seat_count,
    )
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        flight_id=booking.flight_id,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price=float(booking.total_price),
        status=booking.status.value,
        created_at=booking.created_at.isoformat(),
        updated_at=booking.updated_at.isoformat(),
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: UUID, db: DBSession) -> BookingResponse:
    booking = await booking_service.get_booking(db, booking_id)
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        flight_id=booking.flight_id,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price=float(booking.total_price),
        status=booking.status.value,
        created_at=booking.created_at.isoformat(),
        updated_at=booking.updated_at.isoformat(),
    )


@router.get("")
async def list_bookings(
    db: DBSession,
    user_id: UUID = Query(...),
) -> list[BookingResponse]:
    bookings = await booking_service.list_bookings(db, user_id)
    return [
        BookingResponse(
            id=b.id,
            user_id=b.user_id,
            flight_id=b.flight_id,
            passenger_name=b.passenger_name,
            passenger_email=b.passenger_email,
            seat_count=b.seat_count,
            total_price=float(b.total_price),
            status=b.status.value,
            created_at=b.created_at.isoformat(),
            updated_at=b.updated_at.isoformat(),
        )
        for b in bookings
    ]


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: UUID, db: DBSession) -> BookingResponse:
    booking = await booking_service.cancel_booking(db, booking_id)
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        flight_id=booking.flight_id,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price=float(booking.total_price),
        status=booking.status.value,
        created_at=booking.created_at.isoformat(),
        updated_at=booking.updated_at.isoformat(),
    )
