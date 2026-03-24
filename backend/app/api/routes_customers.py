from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Customer
from app.schemas.customer import CustomerResponse

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
