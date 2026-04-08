from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    model_config = {"extra": "forbid"}


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class CustomerResponse(BaseModel):
    id: int
    customer_code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
