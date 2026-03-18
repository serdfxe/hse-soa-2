# ER Diagram — Flight Booking System (3NF)

```mermaid
erDiagram

    %% ── Flight Service DB ──────────────────────────────────────────────────────

    flights {
        UUID id PK
        VARCHAR(10) flight_number "NOT NULL"
        VARCHAR(100) airline "NOT NULL"
        VARCHAR(3) origin "NOT NULL, IATA code"
        VARCHAR(3) destination "NOT NULL, IATA code"
        TIMESTAMPTZ departure_time "NOT NULL"
        TIMESTAMPTZ arrival_time "NOT NULL"
        VARCHAR(10) departure_date "NOT NULL, YYYY-MM-DD (for UNIQUE with flight_number)"
        INTEGER total_seats "NOT NULL, CHECK > 0"
        INTEGER available_seats "NOT NULL, CHECK >= 0, CHECK <= total_seats"
        NUMERIC(12-2) price "NOT NULL, CHECK > 0"
        flight_status_enum status "NOT NULL, DEFAULT SCHEDULED"
    }

    seat_reservations {
        UUID id PK
        UUID flight_id FK
        UUID booking_id "NOT NULL, UNIQUE (from Booking Service)"
        INTEGER seat_count "NOT NULL, CHECK > 0"
        reservation_status_enum status "NOT NULL, DEFAULT ACTIVE"
        TIMESTAMPTZ created_at "NOT NULL, DEFAULT NOW()"
    }

    flights ||--o{ seat_reservations : "has"

    %% ── Booking Service DB ─────────────────────────────────────────────────────

    bookings {
        UUID id PK
        UUID user_id "NOT NULL (external user reference)"
        UUID flight_id "NOT NULL (reference to Flight Service)"
        VARCHAR(255) passenger_name "NOT NULL"
        VARCHAR(255) passenger_email "NOT NULL"
        INTEGER seat_count "NOT NULL, CHECK > 0"
        NUMERIC(12-2) total_price "NOT NULL, CHECK > 0 (price snapshot)"
        booking_status_enum status "NOT NULL, DEFAULT CONFIRMED"
        TIMESTAMPTZ created_at "NOT NULL, DEFAULT NOW()"
        TIMESTAMPTZ updated_at "NOT NULL, DEFAULT NOW()"
    }
```

## 3NF Compliance

| Table | 1NF | 2NF | 3NF |
|---|---|---|---|
| `flights` | All columns atomic; PK = `id` | Single-column PK — trivially satisfied | No transitive deps: `departure_date` is derived from `departure_time` but stored for efficient UNIQUE constraint and indexing — all non-key attributes depend only on `id` |
| `seat_reservations` | All columns atomic; PK = `id` | Single-column PK | `status` and `seat_count` depend only on `id`; `booking_id` is a cross-service foreign key (no FKC in DB, enforced by app logic) |
| `bookings` | All columns atomic; PK = `id` | Single-column PK | `total_price` is a **price snapshot** (not computed from `flight_id` at query time), so no transitive dependency; all attributes depend only on `id` |

## Constraints Summary

| Constraint | Table | Rule |
|---|---|---|
| `ck_flights_total_seats_positive` | `flights` | `total_seats > 0` |
| `ck_flights_available_seats_nonneg` | `flights` | `available_seats >= 0` |
| `ck_flights_available_lte_total` | `flights` | `available_seats <= total_seats` |
| `ck_flights_price_positive` | `flights` | `price > 0` |
| `uq_flight_number_date` | `flights` | `UNIQUE(flight_number, departure_date)` |
| `uq_seat_reservations_booking_id` | `seat_reservations` | `UNIQUE(booking_id)` — one reservation per booking |
| `ck_reservations_seat_count_positive` | `seat_reservations` | `seat_count > 0` |
| `ck_bookings_seat_count_positive` | `bookings` | `seat_count > 0` |
| `ck_bookings_total_price_positive` | `bookings` | `total_price > 0` |
