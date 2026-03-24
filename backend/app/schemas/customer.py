from datetime import datetime

from pydantic import BaseModel


class CustomerResponse(BaseModel):
    id: int
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
