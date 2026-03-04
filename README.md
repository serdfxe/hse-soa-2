# Marketplace API

REST API маркетплейса — FastAPI + PostgreSQL, запускается через Docker Compose.

## Запуск

```bash
docker compose up --build
```

Сервис: `http://localhost:8000` · Swagger UI: `http://localhost:8000/docs`

---

## Стек

- **FastAPI 0.115** + **SQLAlchemy 2.0 async** + **asyncpg** + **PostgreSQL 16**
- **Alembic** — миграции, запускаются автоматически при старте
- **datamodel-codegen** — генерация Pydantic DTO из OpenAPI-спецификации
- **python-jose** / **passlib[bcrypt]** — JWT и хеширование паролей

---

## Архитектура

```
routers (API)  →  services (бизнес-логика)  →  SQLAlchemy ORM  →  PostgreSQL
```

**Кодогенерация.** Источник правды — `openapi/spec.yaml`. Pydantic-модели генерируются командой:

```bash
bash services/marketplace/generate.sh
```

`app/generated/` исключён из git и пересобирается в Dockerfile (Stage 1).

**Миграции.** Версионированные файлы в `migrations/versions/`. Схема включает индексы на часто фильтруемые поля и триггер автообновления `updated_at`.

---

## Аутентификация и авторизация

- **JWT access token** — 30 мин
- **Refresh token** — JWT-подписанный, хеш хранится в БД, ротация при каждом обновлении
- **RBAC** — три роли: `USER`, `SELLER`, `ADMIN`

| Операция | USER | SELLER | ADMIN |
|---|:---:|:---:|:---:|
| `GET /products` | ✓ | ✓ | ✓ |
| `POST /products` | — | свои | ✓ |
| `PUT/DELETE /products/{id}` | — | свои | ✓ |
| `POST /orders` | ✓ | — | ✓ |
| `GET/PUT /orders/{id}`, отмена | свои | — | ✓ |
| `POST /promo-codes` | — | ✓ | ✓ |

---

## Бизнес-логика заказов

Всё выполняется в одной транзакции (`order_service.py`):

1. **Rate limiting** — запрет повторного заказа в течение N минут (через `user_operations`)
2. **Active order check** — нельзя создать заказ при незакрытом (`CREATED`/`PAYMENT_PENDING`)
3. **Валидация товаров** — существуют и `ACTIVE`
4. **Резервирование стока** — `SELECT FOR UPDATE`, `stock -= quantity`
5. **Price snapshot** — фиксируется цена на момент заказа
6. **Промокоды** — `PERCENTAGE` (cap 70%) и `FIXED_AMOUNT`
7. **State machine** — `CREATED → PAYMENT_PENDING → PAID → SHIPPED → COMPLETED`, отмена из `CREATED`/`PAYMENT_PENDING`

---

## Ошибки и логирование

Единый формат ошибок:
```json
{"error_code": "PRODUCT_NOT_FOUND", "message": "Product not found", "details": null}
```

Каждый запрос логируется в JSON с `request_id` (пробрасывается в `X-Request-Id`), методом, эндпоинтом, статусом и временем выполнения.

---

## Структура

```
services/marketplace/
├── openapi/spec.yaml          # OpenAPI 3.0.3 (источник правды)
├── app/
│   ├── generated/             # .gitignore — генерируется из spec.yaml
│   ├── api/                   # routers: auth, products, orders, promo_codes
│   ├── core/                  # config, security, exceptions, dependencies, logging
│   ├── db/                    # session, ORM models
│   └── services/              # auth, product, order, promo
├── migrations/versions/001_initial.py
├── generate.sh
└── Dockerfile
```

---

## E2E сценарий

```bash
BASE=http://localhost:8000

# Регистрация продавца и покупателя
SELLER=$(curl -s -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"email":"seller@test.com","password":"secret123","role":"SELLER"}')
SELLER_TOKEN=$(echo $SELLER | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

BUYER=$(curl -s -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"email":"buyer@test.com","password":"secret123","role":"USER"}')
BUYER_TOKEN=$(echo $BUYER | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Товар
PRODUCT=$(curl -s -X POST $BASE/products -H "Authorization: Bearer $SELLER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Laptop","price":99999.99,"stock":10,"category":"Electronics"}')
PRODUCT_ID=$(echo $PRODUCT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Промокод
curl -s -X POST $BASE/promo-codes -H "Authorization: Bearer $SELLER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code":"SAVE10","discount_type":"PERCENTAGE","discount_value":10,"max_uses":100,"valid_from":"2026-01-01T00:00:00Z","valid_until":"2030-12-31T23:59:59Z"}'

# Заказ с промокодом
ORDER=$(curl -s -X POST $BASE/orders -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"items\":[{\"product_id\":\"$PRODUCT_ID\",\"quantity\":2}],\"promo_code\":\"SAVE10\"}")
ORDER_ID=$(echo $ORDER | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo $ORDER | python3 -m json.tool

# Отмена
curl -s -X POST "$BASE/orders/$ORDER_ID/cancel" -H "Authorization: Bearer $BUYER_TOKEN" | python3 -m json.tool
```
