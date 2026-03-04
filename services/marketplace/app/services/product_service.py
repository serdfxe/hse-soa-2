"""Product CRUD service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccessDeniedError, ProductNotFoundError
from app.db.models import Product, ProductStatus, Role


async def create_product(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    price: float,
    stock: int,
    category: str,
    status: str,
    seller_id: UUID,
) -> Product:
    product = Product(
        name=name,
        description=description,
        price=price,
        stock=stock,
        category=category,
        status=ProductStatus(status),
        seller_id=seller_id,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_product(db: AsyncSession, product_id: UUID) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(product_id)
    return product


async def list_products(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    status: str | None,
    category: str | None,
) -> tuple[list[Product], int]:
    query = select(Product)
    count_query = select(func.count()).select_from(Product)

    if status is not None:
        query = query.where(Product.status == ProductStatus(status))
        count_query = count_query.where(Product.status == ProductStatus(status))
    if category is not None:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    total = (await db.execute(count_query)).scalar_one()
    products = (await db.execute(query.offset(page * size).limit(size))).scalars().all()
    return list(products), total


async def update_product(
    db: AsyncSession,
    product_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
    **fields,
) -> Product:
    product = await get_product(db, product_id)
    _assert_product_ownership(product, actor_id, actor_role)

    for key, value in fields.items():
        if value is not None:
            if key == "status":
                setattr(product, key, ProductStatus(value))
            else:
                setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return product


async def archive_product(
    db: AsyncSession,
    product_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
) -> None:
    product = await get_product(db, product_id)
    _assert_product_ownership(product, actor_id, actor_role)

    product.status = ProductStatus.ARCHIVED
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_product_ownership(product: Product, actor_id: UUID, actor_role: str) -> None:
    """SELLER can only modify their own products; ADMIN has unrestricted access."""
    if actor_role == Role.ADMIN.value:
        return
    if product.seller_id != actor_id:
        raise AccessDeniedError()
