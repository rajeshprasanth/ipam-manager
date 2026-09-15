"""Public web routes: landing page, login, logout."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import utcnow, verify_password
from app.web.deps import get_current_user_web, issue_access_token, redirect, render, verify_csrf
from app.web.oauth import NO_PASSWORD, enabled_providers

router = APIRouter()


@router.get("/", name="home")
async def landing_page(request: Request):
    return render(request, "landing.html", {"active": "home"})


@router.get("/login", name="login")
async def login_page(request: Request):
    if getattr(request.state, "user", None):
        return redirect("/dashboard")
    return render(request, "login.html", {"active": "login", "oauth_providers": list(enabled_providers())})


@router.post("/login", name="login_submit", dependencies=[Depends(verify_csrf)])
async def login_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.hashed_password or user.hashed_password == NO_PASSWORD:
        return redirect("/login", "Invalid username or password.", "error")
    if not verify_password(password, user.hashed_password):
        return redirect("/login", "Invalid username or password.", "error")
    if not user.is_active:
        return redirect("/login", "This account has been disabled.", "error")

    user.last_login = utcnow()
    db.commit()

    response = redirect("/dashboard", f"Welcome back, {user.username}.")
    issue_access_token(response, user)
    return response


@router.get("/logout", name="logout")
async def logout(request: Request, _: User = Depends(get_current_user_web)):
    response = redirect("/")
    response.delete_cookie("access_token", path="/")
    return response