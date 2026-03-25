from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Product
from app.schemas.product import ProductCreateRequest, ProductResponse, ProductUpdateRequest

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)) -> list[ProductResponse]:
    rows = db.query(Product).order_by(Product.id.asc()).all()
    return [ProductResponse.model_validate(r) for r in rows]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})
    return ProductResponse.model_validate(row)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdateRequest, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreateRequest, db: Session = Depends(get_db)) -> ProductResponse:
    exists = db.query(Product).filter(Product.sku == payload.sku).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "SKU_ALREADY_EXISTS", "message": "sku already exists"})

    row = Product(
        sku=payload.sku,
        name=payload.name,
        order_uom=payload.order_uom,
        purchase_uom=payload.purchase_uom,
        invoice_uom=payload.invoice_uom,
        is_catch_weight=payload.is_catch_weight,
        weight_capture_required=payload.weight_capture_required,
        pricing_basis_default=payload.pricing_basis_default,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)
