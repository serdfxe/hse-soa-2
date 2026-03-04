"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-04 00:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Enum types (idempotent) ──────────────────────────────────────────────
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE role_enum AS ENUM ('USER', 'SELLER', 'ADMIN');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE product_status_enum AS ENUM ('ACTIVE', 'INACTIVE', 'ARCHIVED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE order_status_enum AS ENUM (
                'CREATED', 'PAYMENT_PENDING', 'PAID', 'SHIPPED', 'COMPLETED', 'CANCELED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE discount_type_enum AS ENUM ('PERCENTAGE', 'FIXED_AMOUNT');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE operation_type_enum AS ENUM ('CREATE_ORDER', 'UPDATE_ORDER');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # ── users ────────────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id          UUID        PRIMARY KEY,
            email       VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role        role_enum   NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
    ))

    # ── refresh_tokens ───────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id          UUID        PRIMARY KEY,
            user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  VARCHAR(64) NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash"
        " ON refresh_tokens (token_hash)"
    ))

    # ── promo_codes ──────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            id               UUID        PRIMARY KEY,
            code             VARCHAR(20) NOT NULL,
            discount_type    discount_type_enum NOT NULL,
            discount_value   NUMERIC(12, 2) NOT NULL,
            min_order_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
            max_uses         INTEGER     NOT NULL,
            current_uses     INTEGER     NOT NULL DEFAULT 0,
            valid_from       TIMESTAMPTZ NOT NULL,
            valid_until      TIMESTAMPTZ NOT NULL,
            active           BOOLEAN     NOT NULL DEFAULT TRUE
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_promo_codes_code ON promo_codes (code)"
    ))

    # ── products ─────────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS products (
            id          UUID         PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            price       NUMERIC(12, 2) NOT NULL,
            stock       INTEGER      NOT NULL DEFAULT 0,
            category    VARCHAR(100) NOT NULL,
            status      product_status_enum NOT NULL DEFAULT 'ACTIVE',
            seller_id   UUID         NOT NULL REFERENCES users(id),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_products_status    ON products (status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_products_seller_id ON products (seller_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_products_category  ON products (category)"))

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER products_updated_at
        BEFORE UPDATE ON products
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """))

    # ── orders ───────────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS orders (
            id              UUID    PRIMARY KEY,
            user_id         UUID    NOT NULL REFERENCES users(id),
            status          order_status_enum NOT NULL DEFAULT 'CREATED',
            promo_code_id   UUID    REFERENCES promo_codes(id),
            total_amount    NUMERIC(12, 2) NOT NULL DEFAULT 0,
            discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_orders_user_id_status ON orders (user_id, status)"
    ))
    op.execute(sa.text("""
        CREATE OR REPLACE TRIGGER orders_updated_at
        BEFORE UPDATE ON orders
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """))

    # ── order_items ───────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS order_items (
            id             UUID    PRIMARY KEY,
            order_id       UUID    NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id     UUID    NOT NULL REFERENCES products(id),
            quantity       INTEGER NOT NULL,
            price_at_order NUMERIC(12, 2) NOT NULL
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id)"
    ))

    # ── user_operations ───────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_operations (
            id             UUID    PRIMARY KEY,
            user_id        UUID    NOT NULL REFERENCES users(id),
            operation_type operation_type_enum NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_user_operations_user_type_created
        ON user_operations (user_id, operation_type, created_at)
    """))


def downgrade() -> None:
    op.drop_table("user_operations")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("promo_codes")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    for name in ["operation_type_enum", "discount_type_enum", "order_status_enum",
                 "product_status_enum", "role_enum"]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS update_updated_at() CASCADE"))
