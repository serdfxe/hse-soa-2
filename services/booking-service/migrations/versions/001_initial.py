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
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE booking_status_enum AS ENUM ('CONFIRMED', 'CANCELLED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bookings (
            id               UUID           PRIMARY KEY,
            user_id          UUID           NOT NULL,
            flight_id        UUID           NOT NULL,
            passenger_name   VARCHAR(255)   NOT NULL,
            passenger_email  VARCHAR(255)   NOT NULL,
            seat_count       INTEGER        NOT NULL,
            total_price      NUMERIC(12, 2) NOT NULL,
            status           booking_status_enum NOT NULL DEFAULT 'CONFIRMED',
            created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_bookings_seat_count_positive CHECK (seat_count > 0),
            CONSTRAINT ck_bookings_total_price_positive CHECK (total_price > 0)
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_bookings_user_id ON bookings (user_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_bookings_flight_id ON bookings (flight_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_bookings_status ON bookings (status)"))

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER bookings_updated_at
        BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """))


def downgrade() -> None:
    op.drop_table("bookings")
    op.execute(sa.text("DROP TYPE IF EXISTS booking_status_enum"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at() CASCADE"))
