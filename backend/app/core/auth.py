from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


ALLOWED_ROLES = {"admin", "order_entry", "buyer", "supplier", "customer"}
bearer = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "3600"))
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "1209600"))


@dataclass
class AuthContext:
    user_id: str
    role: str


def _encode(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "token expired"}) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "invalid token"}) from e


def issue_tokens(user_id: str, role: str) -> tuple[str, str, int]:
    now = datetime.now(UTC)
    access_exp = now + timedelta(seconds=JWT_ACCESS_TTL_SECONDS)
    refresh_exp = now + timedelta(seconds=JWT_REFRESH_TTL_SECONDS)

    access = _encode(
        {
            "sub": user_id,
            "role": role,
            "type": "access",
            "exp": int(access_exp.timestamp()),
            "iat": int(now.timestamp()),
            "jti": uuid.uuid4().hex,
        }
    )
    refresh = _encode(
        {
            "sub": user_id,
            "role": role,
            "type": "refresh",
            "exp": int(refresh_exp.timestamp()),
            "iat": int(now.timestamp()),
            "jti": uuid.uuid4().hex,
        }
    )
    return access, refresh, JWT_ACCESS_TTL_SECONDS


def parse_refresh_token(token: str) -> dict:
    payload = _decode(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "invalid refresh token"})
    return payload


def get_auth_context(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthContext:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "missing bearer token"})

    payload = _decode(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "invalid access token"})

    role = str(payload.get("role", "")).strip().lower()
    user_id = str(payload.get("sub", "")).strip()
    if not user_id or role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "forbidden"})

    return AuthContext(user_id=user_id, role=role)


def require_roles(*roles: str):
    allowed = {r.lower() for r in roles}

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.role not in allowed:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "forbidden"})
        return ctx

    return _dep
