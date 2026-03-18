"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-18 00:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enum types
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE flight_status_enum AS ENUM ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE reservation_status_enum AS ENUM ('ACTIVE', 'RELEASED', 'EXPIRED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # flights
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS flights (
            id               UUID           PRIMARY KEY,
            flight_number    VARCHAR(10)    NOT NULL,
            airline          VARCHAR(100)   NOT NULL,
            origin           VARCHAR(3)     NOT NULL,
            destination      VARCHAR(3)     NOT NULL,
            departure_time   TIMESTAMPTZ    NOT NULL,
            arrival_time     TIMESTAMPTZ    NOT NULL,
            departure_date   VARCHAR(10)    NOT NULL,
            total_seats      INTEGER        NOT NULL,
            available_seats  INTEGER        NOT NULL,
            price            NUMERIC(12, 2) NOT NULL,
            status           flight_status_enum NOT NULL DEFAULT 'SCHEDULED',
            CONSTRAINT ck_flights_total_seats_positive CHECK (total_seats > 0),
            CONSTRAINT ck_flights_available_seats_nonneg CHECK (available_seats >= 0),
            CONSTRAINT ck_flights_available_lte_total CHECK (available_seats <= total_seats),
            CONSTRAINT ck_flights_price_positive CHECK (price > 0),
            CONSTRAINT uq_flight_number_date UNIQUE (flight_number, departure_date)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_flights_origin_destination_date "
        "ON flights (origin, destination, departure_date)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_flights_status ON flights (status)"
    ))

    # seat_reservations
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS seat_reservations (
            id          UUID       PRIMARY KEY,
            flight_id   UUID       NOT NULL REFERENCES flights(id),
            booking_id  UUID       NOT NULL,
            seat_count  INTEGER    NOT NULL,
            status      reservation_status_enum NOT NULL DEFAULT 'ACTIVE',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_reservations_seat_count_positive CHECK (seat_count > 0),
            CONSTRAINT uq_seat_reservations_booking_id UNIQUE (booking_id)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_reservations_booking_id ON seat_reservations (booking_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_reservations_flight_id_status "
        "ON seat_reservations (flight_id, status)"
    ))


def downgrade() -> None:
    op.drop_table("seat_reservations")
    op.drop_table("flights")
    for name in ["reservation_status_enum", "flight_status_enum"]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))
