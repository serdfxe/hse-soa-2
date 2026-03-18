# Flight Booking System

Распределённая система бронирования авиабилетов из двух микросервисов.

```
Client (REST) → Booking Service :8000 → (gRPC) → Flight Service :50051
                      ↓                                   ↓
                 PostgreSQL                        PostgreSQL + Redis
```

## Запуск

```bash
docker-compose up --build
```

Swagger UI: `http://localhost:8000/docs`

## Тестовые данные

```bash
docker-compose exec flight-db psql -U flightuser -d flightdb -c "
INSERT INTO flights (id, flight_number, airline, origin, destination, departure_time, arrival_time, departure_date, total_seats, available_seats, price) VALUES
  ('a0000000-0000-0000-0000-000000000001', 'SU1234', 'Aeroflot', 'SVO', 'LED', '2026-04-01 08:00:00+00', '2026-04-01 09:30:00+00', '2026-04-01', 150, 150, 4500.00),
  ('a0000000-0000-0000-0000-000000000002', 'SU5678', 'Aeroflot', 'SVO', 'AER', '2026-04-01 12:00:00+00', '2026-04-01 14:30:00+00', '2026-04-01', 200, 200, 7800.00);
"
```

## REST API (Booking Service)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/flights?origin=SVO&destination=LED&date=2026-04-01` | Поиск рейсов |
| GET | `/flights/{id}` | Рейс по ID |
| POST | `/bookings` | Создать бронирование |
| GET | `/bookings/{id}` | Бронирование по ID |
| GET | `/bookings?user_id=...` | Список бронирований пользователя |
| POST | `/bookings/{id}/cancel` | Отменить бронирование |

## Архитектура

| Компонент | Технологии |
|---|---|
| Booking Service | FastAPI, SQLAlchemy async, asyncpg, Alembic |
| Flight Service | gRPC (grpcio), SQLAlchemy async, asyncpg, Alembic |
| Кеш | Redis Sentinel (master + replica + sentinel) |
| БД | PostgreSQL × 2 (раздельные) |

**Реализовано:** gRPC контракт · ER 3NF · Alembic миграции · SELECT FOR UPDATE · API Key auth · Redis Cache-Aside · Retry (exponential backoff) · Redis Sentinel · Circuit Breaker
