"""Promo code endpoints."""

from fastapi import APIRouter

from app.api.mappers import promo_to_response
from app.core.dependencies import DBSession, require_role
from app.generated.models import PromoCodeCreate, PromoCodeResponse
from app.services import promo_service

router = APIRouter(prefix="/promo-codes", tags=["PromoCodes"])


@router.post("", response_model=PromoCodeResponse, status_code=201, dependencies=[require_role("SELLER", "ADMIN")])
async def create_promo_code(body: PromoCodeCreate, db: DBSession) -> PromoCodeResponse:
    promo = await promo_service.create_promo_code(
        db,
        code=body.code,
        discount_type=body.discount_type.value,
        discount_value=body.discount_value,
        min_order_amount=body.min_order_amount if body.min_order_amount is not None else 0.0,
        max_uses=body.max_uses,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )
    await db.commit()
    await db.refresh(promo)
    return promo_to_response(promo)
