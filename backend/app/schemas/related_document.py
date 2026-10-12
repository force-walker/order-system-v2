from typing import Literal

from pydantic import BaseModel, Field


class RelatedDocument(BaseModel):
    type: Literal["order", "delivery", "invoice", "supplier_bill"]
    id: str
    number: str
    status: str | None = None


class RelatedDocumentsResponse(BaseModel):
    orders: list[RelatedDocument] = Field(default_factory=list)
    deliveries: list[RelatedDocument] = Field(default_factory=list)
    invoices: list[RelatedDocument] = Field(default_factory=list)
    supplier_bills: list[RelatedDocument] = Field(default_factory=list)
