from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Customer
from app.schemas.customer import CustomerCreateRequest, CustomerResponse

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerResponse]:
    rows = db.query(Customer).order_by(Customer.id.asc()).all()
    return [CustomerResponse.model_validate(r) for r in rows]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})
    return CustomerResponse.model_validate(row)


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(payload: CustomerCreateRequest, db: Session = Depends(get_db)) -> CustomerResponse:
    exists = db.query(Customer).filter(Customer.code == payload.code).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "CUSTOMER_CODE_ALREADY_EXISTS", "message": "customer code already exists"})

    row = Customer(code=payload.code, name=payload.name, active=payload.active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)
