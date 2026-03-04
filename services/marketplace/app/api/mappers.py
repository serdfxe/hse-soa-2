"""ORM model → generated Pydantic DTO mappers.

All response objects are assembled here so routers stay thin.
Generated models are imported from app.generated.models (codegen output).
"""

from app.db.models import Order, OrderItem, Product, PromoCode
from app.generated.models import (
    OrderItemResponse,
    OrderResponse,
    ProductResponse,
    PromoCodeResponse,
)


def product_to_response(p: Product) -> ProductResponse:
    return ProductResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        price=float(p.price),
        stock=p.stock,
        category=p.category,
        status=p.status.value,
        seller_id=p.seller_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def order_item_to_response(item: OrderItem) -> OrderItemResponse:
    return OrderItemResponse(
        id=item.id,
        product_id=item.product_id,
        quantity=item.quantity,
        price_at_order=float(item.price_at_order),
    )


def order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        items=[order_item_to_response(i) for i in (order.items or [])],
        total_amount=float(order.total_amount),
        discount_amount=float(order.discount_amount),
        promo_code_id=order.promo_code_id,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def promo_to_response(p: PromoCode) -> PromoCodeResponse:
    return PromoCodeResponse(
        id=p.id,
        code=p.code,
        discount_type=p.discount_type.value,
        discount_value=float(p.discount_value),
        min_order_amount=float(p.min_order_amount),
        max_uses=p.max_uses,
        current_uses=p.current_uses,
        valid_from=p.valid_from,
        valid_until=p.valid_until,
        active=p.active,
    )
