from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthContext, auth_error, bearer, email_verification_required, ensure_user_allowed,
    get_auth_context, get_session, hash_password, issue_tokens, verify_password,
)
from app.db.session import get_db
from app.models.auth import User
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
AUTH_COMMON_ERROR_RESPONSES = {
    401: {"model": ApiErrorResponse, "description": "Unauthorized"},
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}
_DUMMY_PASSWORD_HASH = hash_password("not-an-account-password")


@router.post("/register", response_model=MeResponse, status_code=201, responses=AUTH_COMMON_ERROR_RESPONSES)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> MeResponse:
    if email_verification_required():
        raise HTTPException(status_code=503, detail={
            "code": "EMAIL_VERIFICATION_UNAVAILABLE",
            "message": "registration requires email verification; contact the administrator",
        })
    user = User(user_id=payload.user_id.lower(), password_hash=hash_password(payload.password), role="order_entry")
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "USER_ALREADY_EXISTS", "message": "user ID is already registered"}) from exc
    return MeResponse(user_id=user.user_id, role=user.role)


@router.post("/login", response_model=TokenResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.get(User, payload.user_id.lower())
    valid = verify_password(payload.password, user.password_hash if user else _DUMMY_PASSWORD_HASH)
    if not valid or user is None or not user.active:
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "incorrect user ID or password"})
    ensure_user_allowed(user)
    access, refresh, ttl = issue_tokens(user.user_id, user.role, db)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=ttl)


@router.post("/refresh", response_model=TokenResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def refresh(payload: RefreshRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    session = get_session(db, payload.refresh_token, refresh=True, lock=True)
    user = ensure_user_allowed(db.get(User, session.user_id))
    session.revoked = True
    access, refresh_token, ttl = issue_tokens(user.user_id, user.role, db)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=access, refresh_token=refresh_token, expires_in=ttl)


@router.post("/logout", responses=AUTH_COMMON_ERROR_RESPONSES)
def logout(
    payload: RefreshRequest | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if payload is not None:
        session = get_session(db, payload.refresh_token, refresh=True, lock=True, check_user=False)
    elif credentials and credentials.scheme.lower() == "bearer":
        session = get_session(db, credentials.credentials, lock=True, check_user=False)
    else:
        raise auth_error()
    session.revoked = True
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeResponse, responses=AUTH_COMMON_ERROR_RESPONSES)
def me(auth: AuthContext = Depends(get_auth_context)) -> MeResponse:
    return MeResponse(user_id=auth.user_id, role=auth.role)
