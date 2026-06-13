from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail


class ImportRequiredScope(str, Enum):
    always = "always"
    create = "create"
    never = "never"


class ImportFormatField(BaseModel):
    name: str
    label: str
    required: bool
    required_scope: ImportRequiredScope
    description: str | None = None
    example: Any | None = None

    model_config = {"extra": "forbid"}


class ImportFormatResponse(BaseModel):
    entity: str
    fields: list[ImportFormatField] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
