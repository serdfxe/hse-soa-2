"""Order management service with full business logic."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    InsufficientStockError,
    InvalidStateTransitionError,
    OrderHasActiveError,
    OrderLimitExceededError,
    OrderNotFoundError,
    OrderOwnershipViolationError,
    ProductInactiveError,
    ProductNotFoundError,
)
from app.db.models import (
    ALLOWED_TRANSITIONS,
    CANCELLABLE_STATUSES,
    OperationType,
    Order,
    PromoCode,
    OrderItem,
    OrderStatus,
    Product,
    ProductStatus,
    UserOperation,
)
from app.services import promo_service


# ── Public API ────────────────────────────────────────────────────────────────

async def create_order(
    db: AsyncSession,
    *,
    user_id: UUID,
    items: list[dict],  # [{"product_id": UUID, "quantity": int}]
    promo_code: str | None,
) -> Order:
    """Create a new order for a user inside a single transaction."""

    # 1. Rate limiting
    await _check_rate_limit(db, user_id, OperationType.CREATE_ORDER)

    # 2. No active order
    await _check_no_active_order(db, user_id)

    # 3 & 4. Validate products and check stock
    products = await _load_and_validate_products(db, items)

    # 5. Reserve stock (SELECT FOR UPDATE already handled by validation above with lock)
    # 6. Snapshot prices and compute base total
    total_amount, order_items_data = _compute_items(items, products)

    # 7. Apply promo code
    promo_id: UUID | None = None
    discount_amount: float = 0.0

    if promo_code:
        promo, discount_amount = await promo_service.apply_promo(db, promo_code, total_amount)
        total_amount = round(total_amount - discount_amount, 2)
        promo_id = promo.id

    # 5. Commit stock changes (deduct stock)
    for product, qty in _zip_products(items, products):
        product.stock -= qty

    # Build order
    order = Order(
        user_id=user_id,
        status=OrderStatus.CREATED,
        promo_code_id=promo_id,
        total_amount=total_amount,
        discount_amount=discount_amount,
    )
    db.add(order)
    await db.flush()  # get order.id

    for data in order_items_data:
        db.add(OrderItem(order_id=order.id, **data))

    # 8. Record operation
    db.add(UserOperation(user_id=user_id, operation_type=OperationType.CREATE_ORDER))

    await db.commit()
    return await _load_order_with_items(db, order.id)


async def get_order(db: AsyncSession, order_id: UUID, *, actor_id: UUID, actor_role: str) -> Order:
    order = await _get_order_or_404(db, order_id)
    _assert_order_access(order, actor_id, actor_role)
    return order


async def list_orders(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_role: str,
    page: int,
    size: int,
) -> tuple[list[Order], int]:
    from sqlalchemy import func

    query = select(Order)
    count_q = select(func.count()).select_from(Order)

    if actor_role != "ADMIN":
        query = query.where(Order.user_id == actor_id)
        count_q = count_q.where(Order.user_id == actor_id)

    total = (await db.execute(count_q)).scalar_one()
    orders_rows = (await db.execute(query.offset(page * size).limit(size))).scalars().all()

    # Load items for each order
    result_orders = []
    for o in orders_rows:
        result_orders.append(await _load_order_with_items(db, o.id))
    return result_orders, total


async def update_order(
    db: AsyncSession,
    order_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
    items: list[dict],
) -> Order:
    """Replace order items inside a single transaction."""

    # 1. Load & check ownership
    order = await _get_order_or_404(db, order_id)
    _assert_order_ownership(order, actor_id, actor_role)

    # 2. State check — must be CREATED
    if order.status != OrderStatus.CREATED:
        raise InvalidStateTransitionError(order.status.value, "update")

    # 3. Rate limit
    await _check_rate_limit(db, actor_id, OperationType.UPDATE_ORDER)

    # 4. Load existing items and return old stock
    existing_items = await _load_items(db, order_id)
    await _return_stock(db, existing_items)

    # 5 & 6. Validate and reserve new stock
    products = await _load_and_validate_products(db, items)
    total_amount, order_items_data = _compute_items(items, products)

    for product, qty in _zip_products(items, products):
        product.stock -= qty

    # 6. Recalculate promo if any
    discount_amount: float = 0.0
    promo_id: UUID | None = order.promo_code_id

    if promo_id is not None:
        promo_result = await db.execute(select(PromoCode).where(PromoCode.id == promo_id))
        promo = promo_result.scalar_one_or_none()
        if promo and total_amount >= float(promo.min_order_amount):
            discount_amount = promo_service.calculate_discount(promo, total_amount)
        else:
            # Promo no longer valid for new total — remove it from order
            if promo and promo.current_uses > 0:
                promo.current_uses -= 1
            promo_id = None

    final_total = round(total_amount - discount_amount, 2)

    # Delete old items and replace
    for item in existing_items:
        await db.delete(item)
    await db.flush()

    order.total_amount = final_total
    order.discount_amount = discount_amount
    order.promo_code_id = promo_id

    for data in order_items_data:
        db.add(OrderItem(order_id=order.id, **data))

    # 7. Record operation
    db.add(UserOperation(user_id=actor_id, operation_type=OperationType.UPDATE_ORDER))

    await db.commit()
    return await _load_order_with_items(db, order.id)


async def cancel_order(
    db: AsyncSession,
    order_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
) -> Order:
    """Cancel an order: return stock, release promo, set CANCELED status."""

    # 1. Load & check ownership
    order = await _get_order_or_404(db, order_id)
    _assert_order_ownership(order, actor_id, actor_role)

    # 2. Check cancellable state
    if order.status not in CANCELLABLE_STATUSES:
        raise InvalidStateTransitionError(order.status.value, OrderStatus.CANCELED.value)

    # 3. Return stock
    existing_items = await _load_items(db, order_id)
    await _return_stock(db, existing_items)

    # 4. Release promo code usage
    if order.promo_code_id is not None:
        await promo_service.release_promo(db, order.promo_code_id)

    # 5. Set status
    order.status = OrderStatus.CANCELED

    await db.commit()
    return await _load_order_with_items(db, order.id)


async def transition_order_status(
    db: AsyncSession,
    order_id: UUID,
    target_status: str,
    *,
    actor_id: UUID,
    actor_role: str,
) -> Order:
    """General-purpose state transition for ADMIN operations."""
    order = await _get_order_or_404(db, order_id)
    _assert_order_ownership(order, actor_id, actor_role)

    target = OrderStatus(target_status)
    if target not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise InvalidStateTransitionError(order.status.value, target.value)

    order.status = target
    await db.commit()
    return await _load_order_with_items(db, order.id)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _check_rate_limit(db: AsyncSession, user_id: UUID, operation: OperationType) -> None:
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.order_rate_limit_minutes)
    result = await db.execute(
        select(UserOperation)
        .where(
            UserOperation.user_id == user_id,
            UserOperation.operation_type == operation,
            UserOperation.created_at > cutoff,
        )
        .order_by(UserOperation.created_at.desc())
        .limit(1)
    )
    last_op = result.scalar_one_or_none()
    if last_op is not None:
        raise OrderLimitExceededError(settings.order_rate_limit_minutes)


async def _check_no_active_order(db: AsyncSession, user_id: UUID) -> None:
    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.status.in_([OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING]),
        )
    )
    active = result.scalar_one_or_none()
    if active is not None:
        raise OrderHasActiveError(active.id)


async def _load_and_validate_products(
    db: AsyncSession, items: list[dict]
) -> dict[UUID, Product]:
    """
    Load all requested products with a row lock (FOR UPDATE).
    Validate existence and ACTIVE status.
    Returns dict {product_id: Product}.
    """
    product_ids = [item["product_id"] for item in items]

    result = await db.execute(
        select(Product)
        .where(Product.id.in_(product_ids))
        .with_for_update()
    )
    found: dict[UUID, Product] = {p.id: p for p in result.scalars().all()}

    # Validate presence and status
    for item in items:
        pid = item["product_id"]
        product = found.get(pid)
        if product is None:
            raise ProductNotFoundError(pid)
        if product.status != ProductStatus.ACTIVE:
            raise ProductInactiveError(pid)

    # Check stock for all items at once
    shortages = []
    for item in items:
        product = found[item["product_id"]]
        if product.stock < item["quantity"]:
            shortages.append({
                "product_id": str(item["product_id"]),
                "requested": item["quantity"],
                "available": product.stock,
            })

    if shortages:
        raise InsufficientStockError(shortages)

    return found


def _compute_items(
    items: list[dict], products: dict[UUID, Product]
) -> tuple[float, list[dict]]:
    """Compute total amount and build order item data list with price snapshots."""
    total = 0.0
    order_items_data = []

    for item in items:
        product = products[item["product_id"]]
        price = float(product.price)
        qty = item["quantity"]
        total += price * qty
        order_items_data.append({
            "product_id": item["product_id"],
            "quantity": qty,
            "price_at_order": price,
        })

    return round(total, 2), order_items_data


def _zip_products(items: list[dict], products: dict[UUID, Product]):
    for item in items:
        yield products[item["product_id"]], item["quantity"]


async def _load_items(db: AsyncSession, order_id: UUID) -> list[OrderItem]:
    result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    return list(result.scalars().all())


async def _return_stock(db: AsyncSession, items: list[OrderItem]) -> None:
    """Return stock for a list of order items (load products and add back quantity)."""
    if not items:
        return
    product_ids = [item.product_id for item in items]
    result = await db.execute(
        select(Product).where(Product.id.in_(product_ids)).with_for_update()
    )
    products = {p.id: p for p in result.scalars().all()}
    for item in items:
        product = products.get(item.product_id)
        if product:
            product.stock += item.quantity


async def _get_order_or_404(db: AsyncSession, order_id: UUID) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise OrderNotFoundError()
    return order


async def _load_order_with_items(db: AsyncSession, order_id: UUID) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one()
    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    order.items = list(items_result.scalars().all())
    return order


def _assert_order_access(order: Order, actor_id: UUID, actor_role: str) -> None:
    """Check read access: USER can only see their own orders."""
    if actor_role == "ADMIN":
        return
    if order.user_id != actor_id:
        raise OrderNotFoundError()  # 404, not 403, to avoid leaking order existence


def _assert_order_ownership(order: Order, actor_id: UUID, actor_role: str) -> None:
    """Check write access: return 403 if the order belongs to another user."""
    if actor_role == "ADMIN":
        return
    if order.user_id != actor_id:
        raise OrderOwnershipViolationError()
