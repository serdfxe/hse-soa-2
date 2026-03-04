"""Order management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.mappers import order_to_response
from app.core.dependencies import AuthUser, DBSession, require_role
from app.generated.models import OrderCreate, OrderListResponse, OrderResponse, OrderUpdate
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])

_user_or_admin = require_role("USER", "ADMIN")


@router.get("", response_model=OrderListResponse, dependencies=[_user_or_admin])
async def list_orders(
    db: DBSession,
    user: AuthUser,
    page: int = Query(default=0, ge=0),
    size: int = Query(default=20, ge=1, le=100),
) -> OrderListResponse:
    orders, total = await order_service.list_orders(
        db, actor_id=user.user_id, actor_role=user.role, page=page, size=size
    )
    return OrderListResponse(
        items=[order_to_response(o) for o in orders],
        total_elements=total,
        page=page,
        size=size,
    )


@router.post("", response_model=OrderResponse, status_code=201, dependencies=[_user_or_admin])
async def create_order(body: OrderCreate, db: DBSession, user: AuthUser) -> OrderResponse:
    items = [{"product_id": item.product_id, "quantity": item.quantity} for item in body.items]
    order = await order_service.create_order(
        db,
        user_id=user.user_id,
        items=items,
        promo_code=body.promo_code,
    )
    return order_to_response(order)


@router.get("/{order_id}", response_model=OrderResponse, dependencies=[_user_or_admin])
async def get_order(order_id: UUID, db: DBSession, user: AuthUser) -> OrderResponse:
    order = await order_service.get_order(db, order_id, actor_id=user.user_id, actor_role=user.role)
    return order_to_response(order)


@router.put("/{order_id}", response_model=OrderResponse, dependencies=[_user_or_admin])
async def update_order(order_id: UUID, body: OrderUpdate, db: DBSession, user: AuthUser) -> OrderResponse:
    items = [{"product_id": item.product_id, "quantity": item.quantity} for item in body.items]
    order = await order_service.update_order(
        db,
        order_id,
        actor_id=user.user_id,
        actor_role=user.role,
        items=items,
    )
    return order_to_response(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse, dependencies=[_user_or_admin])
async def cancel_order(order_id: UUID, db: DBSession, user: AuthUser) -> OrderResponse:
    order = await order_service.cancel_order(
        db, order_id, actor_id=user.user_id, actor_role=user.role
    )
    return order_to_response(order)
