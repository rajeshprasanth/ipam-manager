"""Admin-only web routes for portal user management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ROLE_ADMIN, User
from app.schemas import PasswordReset, UserCreate, UserUpdate
from app.security import get_password_hash
from app.web.deps import redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, model_to_form

router = APIRouter()


def _last_admin_guard(db: Session, target: User, new_role: str | None = None, new_active: bool | None = None) -> str | None:
    """Return an error message if demoting/disabling the target would leave zero active admins."""
    if target.role != ROLE_ADMIN:
        return None
    becoming_non_admin = new_role is not None and new_role != ROLE_ADMIN
    becoming_inactive = new_active is False
    if not (becoming_non_admin or becoming_inactive):
        return None
    # Count active admins excluding the target itself.
    count = db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_ADMIN, User.is_active.is_(True))) or 0
    if count <= 1:
        return "Cannot change the last active administrator."
    return None


@router.get("/users", name="users", dependencies=[Depends(require_admin_web)])
async def users_page(request: Request, db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return render(request, "users/list.html", {"active": "users", "items": users})


@router.get("/users/add", name="users_add", dependencies=[Depends(require_admin_web)])
async def add_user_page(request: Request):
    return render(request, "users/form.html", {"active": "users", "mode": "add", "form_data": {}})


@router.post("/users/add", name="users_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_user_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)
    try:
        payload = UserCreate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "users/form.html", {
            "active": "users", "mode": "add", "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    dup = db.scalar(select(User).where(or_(User.username == payload.username, User.email == payload.email)))
    if dup:
        return render(request, "users/form.html", {
            "active": "users", "mode": "add", "form_data": form_data,
            "errors": ["A user with that username or email already exists."],
        })

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
    return redirect("/users", f"User {user.username} created successfully.", "success")


@router.get("/users/{user_id}/edit", name="users_edit", dependencies=[Depends(require_admin_web)])
async def edit_user_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    return render(request, "users/form.html", {
        "active": "users", "mode": "edit", "item": user, "form_data": model_to_form(user),
    })


@router.post("/users/{user_id}/edit", name="users_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_user_submit(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)

    current_user: User = request.state.user
    form = await request.form()
    form_data = dict(form)
    try:
        payload = UserUpdate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "users/form.html", {
            "active": "users", "mode": "edit", "item": user, "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    # Lock-out guards: never disable yourself, never remove the last admin.
    if user.id == current_user.id and (payload.role != ROLE_ADMIN or not payload.is_active):
        return render(request, "users/form.html", {
            "active": "users", "mode": "edit", "item": user, "form_data": form_data,
            "errors": ["You cannot demote or disable your own account."],
        })

    guard_error = _last_admin_guard(db, user, payload.role, payload.is_active)
    if guard_error:
        return render(request, "users/form.html", {
            "active": "users", "mode": "edit", "item": user, "form_data": form_data,
            "errors": [guard_error],
        })

    dup = db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
    if dup:
        return render(request, "users/form.html", {
            "active": "users", "mode": "edit", "item": user, "form_data": form_data,
            "errors": ["That email address is already in use."],
        })

    user.email = payload.email
    user.full_name = payload.full_name
    user.role = payload.role
    user.is_active = payload.is_active
    db.commit()
    return redirect("/users", f"User {user.username} updated successfully.")


@router.post("/users/{user_id}/toggle-status", name="users_toggle",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def toggle_user_status(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)

    current_user: User = request.state.user
    if user.id == current_user.id:
        return redirect("/users", "You cannot disable your own account.", "error")

    intended_active = not user.is_active
    guard_error = _last_admin_guard(db, user, new_active=intended_active)
    if guard_error:
        return redirect("/users", guard_error, "error")

    user.is_active = intended_active
    db.commit()
    state = "enabled" if user.is_active else "disabled"
    return redirect("/users", f"User {user.username} {state}.")


@router.post("/users/{user_id}/reset-password", name="users_reset_password",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def reset_user_password(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    try:
        payload = PasswordReset.model_validate(clean_form(dict(form)))
    except ValidationError as exc:
        return redirect("/users", "; ".join(err["msg"] for err in exc.errors()), "error")

    user.hashed_password = get_password_hash(payload.password)
    db.commit()
    return redirect("/users", f"Password reset for {user.username}.")