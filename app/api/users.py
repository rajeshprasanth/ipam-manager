"""REST API routes for portal user management (admin only)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin_api
from app.models import ROLE_ADMIN, User
from app.schemas import PasswordReset, UserCreate, UserOut, UserUpdate
from app.security import get_password_hash

router = APIRouter()


def _last_admin_guard(db: Session, target: User, new_role: str | None = None, new_active: bool | None = None) -> str | None:
    if target.role != ROLE_ADMIN:
        return None
    becoming_non_admin = new_role is not None and new_role != ROLE_ADMIN
    becoming_inactive = new_active is False
    if not (becoming_non_admin or becoming_inactive):
        return None
    count = db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_ADMIN, User.is_active.is_(True))) or 0
    if count <= 1:
        return "Cannot change the last active administrator."
    return None


@router.get("", response_model=list[UserOut], name="api_users_list")
async def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin_api)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.get("/{user_id}", response_model=UserOut, name="api_users_get")
async def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin_api)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=UserOut, status_code=201, name="api_users_create")
async def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin_api)):
    dup = db.scalar(select(User).where(or_(User.username == payload.username, User.email == payload.email)))
    if dup:
        raise HTTPException(status_code=409, detail="Username or email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut, name="api_users_update")
async def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin_api)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and (payload.role != ROLE_ADMIN or not payload.is_active):
        raise HTTPException(status_code=400, detail="You cannot demote or disable your own account")

    guard_error = _last_admin_guard(db, user, payload.role, payload.is_active)
    if guard_error:
        raise HTTPException(status_code=400, detail=guard_error)

    dup = db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
    if dup:
        raise HTTPException(status_code=409, detail="Email already in use")

    user.email = payload.email
    user.full_name = payload.full_name
    user.role = payload.role
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", name="api_users_reset_password")
async def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db),
                         _: User = Depends(require_admin_api)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash(payload.password)
    db.commit()
    return {"status": "ok"}