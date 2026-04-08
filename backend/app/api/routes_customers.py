from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.db.session import get_db
from app.models.entities import Customer
from app.schemas.common import ApiErrorResponse
from app.schemas.customer import CustomerCreateRequest, CustomerResponse, CustomerUpdateRequest

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])

CUSTOMER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[CustomerResponse])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerResponse]:
    rows = db.query(Customer).order_by(Customer.id.asc()).all()
    return [CustomerResponse.model_validate(r) for r in rows]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    responses={**CUSTOMER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})
    return CustomerResponse.model_validate(row)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    responses={**CUSTOMER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_customer(customer_id: int, payload: CustomerUpdateRequest, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    responses={
        **CUSTOMER_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_customer(payload: CustomerCreateRequest, db: Session = Depends(get_db)) -> CustomerResponse:
    customer_code = generate_next_code(db, Customer, "customer_code", prefix="CUST-")

    exists = db.query(Customer).filter(Customer.customer_code == customer_code).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "CUSTOMER_CODE_ALREADY_EXISTS", "message": "customer code already exists"})

    row = Customer(customer_code=customer_code, name=payload.name, active=payload.active)
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)
