"""Shared FastAPI dependencies: DB sessions, authentication, role guards."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ROLE_ADMIN, User
from app.security import decode_access_token


def extract_token(request: Request) -> str | None:
    """Read a bearer token from the Authorization header or access_token cookie."""
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.cookies.get("access_token")


def get_user_by_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user_api(request: Request, db: Session = Depends(get_db)) -> User:
    """API dependency: require a valid token (header or cookie)."""
    user = get_user_by_token(db, extract_token(request))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin_api(user: User = Depends(get_current_user_api)) -> User:
    """API dependency: require the admin role."""
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user