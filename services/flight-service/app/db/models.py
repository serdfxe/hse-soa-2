"""SQLAlchemy ORM models for Flight Service."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FlightStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint("flight_number", "departure_date", name="uq_flight_number_date"),
        CheckConstraint("total_seats > 0", name="ck_flights_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="ck_flights_available_seats_nonneg"),
        CheckConstraint("available_seats <= total_seats", name="ck_flights_available_lte_total"),
        CheckConstraint("price > 0", name="ck_flights_price_positive"),
        Index("ix_flights_origin_destination_date", "origin", "destination", "departure_date"),
        Index("ix_flights_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number: Mapped[str] = mapped_column(String(10), nullable=False)
    airline: Mapped[str] = mapped_column(String(100), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    departure_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD, for unique constraint
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    status: Mapped[FlightStatus] = mapped_column(
        Enum(FlightStatus, name="flight_status_enum"), nullable=False, default=FlightStatus.SCHEDULED
    )

    reservations: Mapped[list["SeatReservation"]] = relationship(
        "SeatReservation", back_populates="flight", lazy="noload"
    )


class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    __table_args__ = (
        CheckConstraint("seat_count > 0", name="ck_reservations_seat_count_positive"),
        Index("ix_reservations_booking_id", "booking_id"),
        Index("ix_reservations_flight_id_status", "flight_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flights.id"), nullable=False
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum"),
        nullable=False,
        default=ReservationStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    flight: Mapped["Flight"] = relationship("Flight", back_populates="reservations", lazy="noload")
