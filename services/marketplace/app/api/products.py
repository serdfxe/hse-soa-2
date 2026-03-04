"""Product CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.mappers import product_to_response
from app.core.dependencies import AuthUser, DBSession, require_role
from app.generated.models import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductStatus,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    db: DBSession,
    page: int = Query(default=0, ge=0),
    size: int = Query(default=20, ge=1, le=100),
    status: ProductStatus | None = Query(default=None),
    category: str | None = Query(default=None, max_length=100),
) -> ProductListResponse:
    products, total = await product_service.list_products(
        db,
        page=page,
        size=size,
        status=status.value if status else None,
        category=category,
    )
    return ProductListResponse(
        items=[product_to_response(p) for p in products],
        total_elements=total,
        page=page,
        size=size,
    )


@router.post("", response_model=ProductResponse, status_code=201, dependencies=[require_role("SELLER", "ADMIN")])
async def create_product(body: ProductCreate, db: DBSession, user: AuthUser) -> ProductResponse:
    product = await product_service.create_product(
        db,
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
        category=body.category,
        status=body.status.value if body.status else "ACTIVE",
        seller_id=user.user_id,
    )
    return product_to_response(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: UUID, db: DBSession) -> ProductResponse:
    product = await product_service.get_product(db, product_id)
    return product_to_response(product)


@router.put("/{product_id}", response_model=ProductResponse, dependencies=[require_role("SELLER", "ADMIN")])
async def update_product(product_id: UUID, body: ProductUpdate, db: DBSession, user: AuthUser) -> ProductResponse:
    fields = body.model_dump(exclude_none=True)
    if "status" in fields and fields["status"] is not None:
        fields["status"] = fields["status"].value if hasattr(fields["status"], "value") else fields["status"]

    product = await product_service.update_product(
        db,
        product_id,
        actor_id=user.user_id,
        actor_role=user.role,
        **fields,
    )
    return product_to_response(product)


@router.delete("/{product_id}", status_code=204, dependencies=[require_role("SELLER", "ADMIN")])
async def delete_product(product_id: UUID, db: DBSession, user: AuthUser) -> None:
    await product_service.archive_product(
        db,
        product_id,
        actor_id=user.user_id,
        actor_role=user.role,
    )
