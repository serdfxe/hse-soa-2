"""Promo code service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PromoCodeAlreadyExistsError, PromoCodeInvalidError, PromoCodeMinAmountError
from app.db.models import DiscountType, PromoCode

# Maximum percentage discount allowed (70%)
MAX_PERCENTAGE_DISCOUNT = 0.70


async def create_promo_code(
    db: AsyncSession,
    *,
    code: str,
    discount_type: str,
    discount_value: float,
    min_order_amount: float,
    max_uses: int,
    valid_from: datetime,
    valid_until: datetime,
) -> PromoCode:
    promo = PromoCode(
        code=code.upper(),
        discount_type=DiscountType(discount_type),
        discount_value=discount_value,
        min_order_amount=min_order_amount,
        max_uses=max_uses,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    db.add(promo)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise PromoCodeAlreadyExistsError()
    return promo


async def get_active_promo(db: AsyncSession, code: str) -> PromoCode:
    """Return a valid, active, non-exhausted promo code or raise PromoCodeInvalidError."""
    now = datetime.now(UTC)
    result = await db.execute(select(PromoCode).where(PromoCode.code == code.upper()))
    promo = result.scalar_one_or_none()

    if promo is None:
        raise PromoCodeInvalidError("Promo code not found")
    if not promo.active:
        raise PromoCodeInvalidError("Promo code is inactive")
    if promo.current_uses >= promo.max_uses:
        raise PromoCodeInvalidError("Promo code has been exhausted")
    if not (promo.valid_from <= now <= promo.valid_until):
        raise PromoCodeInvalidError("Promo code has expired or is not yet valid")

    return promo


def calculate_discount(promo: PromoCode, total_amount: float) -> float:
    """Compute the discount amount.

    PERCENTAGE: discount = total * rate, capped at 70%.
    FIXED_AMOUNT: discount = min(value, total).
    """
    if promo.discount_type == DiscountType.PERCENTAGE:
        rate = float(promo.discount_value) / 100.0
        rate = min(rate, MAX_PERCENTAGE_DISCOUNT)
        return round(total_amount * rate, 2)
    else:  # FIXED_AMOUNT
        return round(min(float(promo.discount_value), total_amount), 2)


async def apply_promo(
    db: AsyncSession,
    code: str,
    total_amount: float,
) -> tuple[PromoCode, float]:
    """Validate promo, check min amount, calculate discount. Does NOT commit."""
    promo = await get_active_promo(db, code)

    if total_amount < float(promo.min_order_amount):
        raise PromoCodeMinAmountError(float(promo.min_order_amount), total_amount)

    discount = calculate_discount(promo, total_amount)
    promo.current_uses += 1
    return promo, discount


async def release_promo(db: AsyncSession, promo_code_id: UUID) -> None:
    """Decrement usage when an order is cancelled or promo is removed. Does NOT commit."""
    result = await db.execute(select(PromoCode).where(PromoCode.id == promo_code_id))
    promo = result.scalar_one_or_none()
    if promo and promo.current_uses > 0:
        promo.current_uses -= 1
