from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail
