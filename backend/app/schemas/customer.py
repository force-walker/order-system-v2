from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    active: bool = True


class CustomerResponse(BaseModel):
    id: int
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
