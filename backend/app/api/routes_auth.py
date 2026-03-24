from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import ALLOWED_ROLES, AuthContext, get_auth_context, issue_tokens, parse_refresh_token
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "forbidden"})

    access, refresh, ttl = issue_tokens(payload.user_id, role)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=ttl)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest) -> TokenResponse:
    decoded = parse_refresh_token(payload.refresh_token)
    access, refresh_token, ttl = issue_tokens(str(decoded["sub"]), str(decoded["role"]))
    return TokenResponse(access_token=access, refresh_token=refresh_token, expires_in=ttl)


@router.post("/logout")
def logout(_: RefreshRequest) -> dict[str, bool]:
    # stateless JWT in MVP: client-side token discard
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(auth: AuthContext = Depends(get_auth_context)) -> MeResponse:
    return MeResponse(user_id=auth.user_id, role=auth.role)
