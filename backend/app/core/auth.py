from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import AuthSession, User

ALLOWED_ROLES = {"admin", "order_entry", "buyer", "supplier", "customer"}
bearer = HTTPBearer(auto_error=False)
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "3600"))
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "1209600"))


@dataclass
class AuthContext:
    user_id: str
    role: str


def email_verification_required() -> bool:
    # Unknown nonempty values fail closed.
    return os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").strip().lower() not in {"", "0", "false", "no", "off"}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000)
    return "pbkdf2_sha256$600000$" + salt + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def auth_error() -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "invalid or expired session"})


def ensure_user_allowed(user: User | None) -> User:
    if user is None or not user.active or user.role not in ALLOWED_ROLES:
        raise auth_error()
    if email_verification_required() and not user.email_verified:
        raise HTTPException(status_code=403, detail={"code": "EMAIL_VERIFICATION_REQUIRED", "message": "email verification is required"})
    return user


def issue_tokens(user_id: str, role: str, db: Session) -> tuple[str, str, int]:
    user = ensure_user_allowed(db.get(User, user_id))
    if user.role != role:
        raise auth_error()
    access, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    now = utcnow()
    db.add(AuthSession(
        user_id=user.user_id, access_hash=token_hash(access), refresh_hash=token_hash(refresh),
        access_expires_at=now + timedelta(seconds=JWT_ACCESS_TTL_SECONDS),
        refresh_expires_at=now + timedelta(seconds=JWT_REFRESH_TTL_SECONDS),
    ))
    return access, refresh, JWT_ACCESS_TTL_SECONDS


def get_session(db: Session, token: str, *, refresh: bool = False, lock: bool = False, check_user: bool = True) -> AuthSession:
    column = AuthSession.refresh_hash if refresh else AuthSession.access_hash
    query = select(AuthSession).where(column == token_hash(token))
    if lock:
        query = query.with_for_update()
    session = db.scalar(query)
    expires = None if session is None else (session.refresh_expires_at if refresh else session.access_expires_at)
    if session is None or session.revoked or expires <= utcnow() or session.refresh_expires_at <= utcnow():
        raise auth_error()
    if check_user:
        ensure_user_allowed(db.get(User, session.user_id))
    return session


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise auth_error()
    session = get_session(db, credentials.credentials)
    user = ensure_user_allowed(db.get(User, session.user_id))
    return AuthContext(user_id=user.user_id, role=user.role)


def require_roles(*roles: str):
    allowed = {r.lower() for r in roles}

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.role not in allowed:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "forbidden"})
        return ctx

    return _dep
