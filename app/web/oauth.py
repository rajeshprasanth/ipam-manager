"""OAuth 2.0 sign-in for Google and GitHub.

Implements the authorization-code flow entirely with httpx (no extra OAuth
dependency). Provider accounts are matched to portal users by verified email;
new users are created with the read-only ``viewer`` role and cannot use a
local password.
"""
import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ROLE_VIEWER, User
from app.security import utcnow
from app.web.deps import issue_access_token, redirect

router = APIRouter()

PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "label": "Google",
        "icon": "bi-google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "client_id_attr": "GOOGLE_CLIENT_ID",
        "client_secret_attr": "GOOGLE_CLIENT_SECRET",
    },
    "github": {
        "label": "GitHub",
        "icon": "bi-github",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
        "client_id_attr": "GITHUB_CLIENT_ID",
        "client_secret_attr": "GITHUB_CLIENT_SECRET",
    },
}

NO_PASSWORD = "!"  # sentinel: no local password for OAuth-provisioned accounts


def enabled_providers() -> list[dict[str, str]]:
    """Return the providers configured with both client id and secret."""
    for key, cfg in PROVIDERS.items():
        if getattr(settings, cfg["client_id_attr"]) and getattr(settings, cfg["client_secret_attr"]):
            yield {"key": key, "label": cfg["label"], "icon": cfg["icon"]}


def _client_id(cfg: dict[str, str]) -> str:
    return getattr(settings, cfg["client_id_attr"])


def _client_secret(cfg: dict[str, str]) -> str:
    return getattr(settings, cfg["client_secret_attr"])


def _redirect_uri(request: Request, key: str) -> str:
    base = (settings.OAUTH_BASE_URL or str(request.base_url)).rstrip("/")
    return f"{base}/auth/callback/{key}"


def _state_cookie(key: str) -> str:
    return f"oauth_state_{key}"


# --------------------------------------------------------------------------- #
# Handoff: /login/{google,github}
# --------------------------------------------------------------------------- #
def _start_handoff(request: Request, key: str):
    cfg = PROVIDERS[key]
    if not (_client_id(cfg) and _client_secret(cfg)):
        return redirect("/login", f"{cfg['label']} sign-in is not configured.", "error")
    if getattr(request.state, "user", None):
        return redirect("/dashboard")

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": _client_id(cfg),
        "redirect_uri": _redirect_uri(request, key),
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    response = RedirectResponse(cfg["auth_url"] + "?" + urlencode(params), status_code=302)
    response.set_cookie(
        _state_cookie(key), state,
        httponly=True, path="/",
        samesite=settings.COOKIE_SAMESITE, secure=settings.COOKIE_SECURE,
    )
    return response


# --------------------------------------------------------------------------- #
# Provider exchange (secrets never leave the server)
# --------------------------------------------------------------------------- #
def _exchange_code(key: str, code: str, redirect_uri: str) -> str:
    cfg = PROVIDERS[key]
    resp = httpx.post(
        cfg["token_url"],
        data={
            "client_id": _client_id(cfg),
            "client_secret": _client_secret(cfg),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError("Provider did not return an access token")
    return token


def _oauth_get(url: str, token: str):
    return httpx.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15)


def _fetch_email_and_name(key: str, token: str) -> tuple[str, str | None]:
    cfg = PROVIDERS[key]
    if key == "github":
        info = _oauth_get(cfg["userinfo_url"], token).json()
        email = info.get("email")
        if not email:
            emails = _oauth_get("https://api.github.com/user/emails", token).json()
            email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
        return (email or "").strip().lower(), info.get("name") or info.get("login")

    info = _oauth_get(cfg["userinfo_url"], token).json()
    if not info.get("email_verified"):
        raise ValueError("Email is not verified by the provider")
    return (info.get("email") or "").strip().lower(), info.get("name")


# --------------------------------------------------------------------------- #
# Account provisioning
# --------------------------------------------------------------------------- #
def _unique_username(db: Session, base: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]", "", (base or "user"))[:32] or "user"
    candidate, suffix = clean, 1
    while db.scalar(select(User).where(User.username == candidate)):
        suffix += 1
        candidate = f"{clean[: 31 - len(str(suffix))]}.{suffix}"
    return candidate


def _get_or_create_oauth_user(db: Session, email: str, full_name: str | None) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(
            username=_unique_username(db, email.partition("@")[0]),
            email=email,
            full_name=full_name,
            hashed_password=NO_PASSWORD,
            role=ROLE_VIEWER,
            is_active=True,
        )
        db.add(user)
        db.flush()
    return user


# --------------------------------------------------------------------------- #
# Callback: /auth/callback/{google,github}
# --------------------------------------------------------------------------- #
def _handle_callback(request: Request, key: str, db: Session):
    cookie = _state_cookie(key)

    def _deny(message: str):
        response = redirect("/login", message, "error")
        response.delete_cookie(cookie, path="/")
        return response

    if request.query_params.get("error"):
        return _deny(f"{PROVIDERS[key]['label']} sign-in was cancelled or failed.")

    state = request.query_params.get("state", "")
    expected = request.cookies.get(cookie, "")
    if not state or not expected or not secrets.compare_digest(state, expected):
        return _deny("Sign-in state mismatch. Please try again.")

    try:
        token = _exchange_code(key, request.query_params.get("code", ""), _redirect_uri(request, key))
        email, full_name = _fetch_email_and_name(key, token)
        if not email:
            raise ValueError("Provider did not return an email address")
    except Exception:
        return _deny(f"Could not complete {PROVIDERS[key]['label']} sign-in.")

    user = _get_or_create_oauth_user(db, email, full_name)
    if not user.is_active:
        return _deny("This account has been disabled.")

    user.last_login = utcnow()
    db.commit()

    response = redirect("/dashboard", f"Signed in with {PROVIDERS[key]['label']}. Welcome, {user.username}.")
    issue_access_token(response, user)
    response.delete_cookie(cookie, path="/")
    return response


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/login/google", name="oauth_login_google", include_in_schema=False)
async def oauth_login_google(request: Request):
    return _start_handoff(request, "google")


@router.get("/login/github", name="oauth_login_github", include_in_schema=False)
async def oauth_login_github(request: Request):
    return _start_handoff(request, "github")


@router.get("/auth/callback/google", name="oauth_callback_google", include_in_schema=False)
async def oauth_callback_google(request: Request, db: Session = Depends(get_db)):
    return _handle_callback(request, "google", db)


@router.get("/auth/callback/github", name="oauth_callback_github", include_in_schema=False)
async def oauth_callback_github(request: Request, db: Session = Depends(get_db)):
    return _handle_callback(request, "github", db)