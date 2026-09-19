from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=3, max_length=128, pattern=r"^[a-zA-Z0-9_.@+-]+$")
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=12, max_length=128)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=2048)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    user_id: str
    role: str
