from pydantic import BaseModel


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    detail: ApiErrorDetail
