"""Product CRUD + AI classification trigger (Workflow A)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import (
    ClassifyRequest,
    ClassifyResult,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from ..seed import ensure_demo_user
from ..services.classification import classify

router = APIRouter(prefix="/api/products", tags=["products"])


def _to_out(product: models.Product) -> ProductOut:
    open_alerts = sum(1 for a in product.alerts if not a.is_read)
    out = ProductOut.model_validate(product)
    out.open_alerts = open_alerts
    return out


@router.post("/classify", response_model=ClassifyResult)
def classify_product(payload: ClassifyRequest) -> ClassifyResult:
    """Send a free-text description to the LLM and return a draft labeling."""
    return classify(payload.description, payload.name)


@router.get("", response_model=list[ProductOut])
def list_products(
    user_id: str | None = None, db: Session = Depends(get_db)
) -> list[ProductOut]:
    stmt = select(models.Product)
    if user_id:
        stmt = stmt.where(models.Product.user_id == user_id)
    products = db.execute(stmt.order_by(models.Product.created_at.desc())).scalars().all()
    return [_to_out(p) for p in products]


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductOut:
    user_id = payload.user_id
    if not user_id:
        user_id = ensure_demo_user(db).id
    elif not db.get(models.User, user_id):
        raise HTTPException(404, "user not found")

    data = payload.model_dump(exclude={"user_id"})
    product = models.Product(user_id=user_id, **data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductOut:
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "product not found")
    return _to_out(product)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str, payload: ProductUpdate, db: Session = Depends(get_db)
) -> ProductOut:
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "product not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.delete("/{product_id}", status_code=204, response_class=Response)
def delete_product(product_id: str, db: Session = Depends(get_db)) -> Response:
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(404, "product not found")
    db.delete(product)
    db.commit()
    return Response(status_code=204)
