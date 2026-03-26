from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import ALLOWED_ROLES, AuthContext, get_auth_context, issue_tokens, parse_refresh_token
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

AUTH_COMMON_ERROR_RESPONSES = {
    401: {"model": ApiErrorResponse, "description": "Unauthorized"},
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.post("/login", response_model=TokenResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def login(payload: LoginRequest) -> TokenResponse:
    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail={"code": "INVALID_ROLE", "message": "invalid role"})

    access, refresh, ttl = issue_tokens(payload.user_id, role)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=ttl)


@router.post("/refresh", response_model=TokenResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def refresh(payload: RefreshRequest) -> TokenResponse:
    decoded = parse_refresh_token(payload.refresh_token)
    access, refresh_token, ttl = issue_tokens(str(decoded["sub"]), str(decoded["role"]))
    return TokenResponse(access_token=access, refresh_token=refresh_token, expires_in=ttl)


@router.post("/logout", responses={422: {"model": ApiErrorResponse, "description": "Validation Error"}})
def logout(_: RefreshRequest) -> dict[str, bool]:
    # stateless JWT in MVP: client-side token discard
    return {"ok": True}


@router.get("/me", response_model=MeResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def me(auth: AuthContext = Depends(get_auth_context)) -> MeResponse:
    return MeResponse(user_id=auth.user_id, role=auth.role)
