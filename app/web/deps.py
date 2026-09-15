"""Web-layer helpers: rendering, flash messages, CSRF, and auth guards."""
import base64
import json
import secrets
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models import ROLE_ADMIN, User
from app.security import create_access_token

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

FLASH_COOKIE = "ipam_flash"
CSRF_COOKIE = "ipam_csrf"

templates.env.filters["dt"] = lambda v: v.strftime("%Y-%m-%dT%H:%M") if v else ""


# --------------------------------------------------------------------------- #
# Flash messages (stored in a signed opaque cookie)
# --------------------------------------------------------------------------- #
def _encode_flash(category: str, message: str) -> str:
    raw = json.dumps([category, message]).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_flash(value: str | None) -> list[tuple[str, str]]:
    if not value:
        return []
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))
        return [(str(data[0]), str(data[1]))]
    except Exception:
        return []


def redirect(url: str, message: str | None = None, category: str = "success") -> RedirectResponse:
    response = RedirectResponse(url=url, status_code=303)
    if message:
        _set_cookie(response, FLASH_COOKIE, _encode_flash(category, message), http_only=True)
    return response


# --------------------------------------------------------------------------- #
# URL helpers available inside templates
# --------------------------------------------------------------------------- #
def _build_url(request: Request, name: str, **path_params: object) -> str:
    return str(request.url_for(name, **path_params))


def _qs(**params: object) -> str:
    parts = [(str(k), quote(str(v))) for k, v in params.items() if v not in (None, "")]
    return "&".join(f"{k}={v}" for k, v in parts)


def _static(path: str) -> str:
    return "/static/" + path.lstrip("/")


# --------------------------------------------------------------------------- #
# CSRF helpers
# --------------------------------------------------------------------------- #
def _set_cookie(response, key: str, value: str, http_only: bool = False) -> None:
    response.set_cookie(
        key,
        value,
        httponly=http_only,
        path="/",
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
    )


def _ensure_csrf(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE)
    if not token:
        token = secrets.token_urlsafe(32)
    return token


async def verify_csrf(request: Request) -> None:
    """Dependency for mutating web routes: validates the CSRF token."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    form = await request.form()
    token = form.get("_csrf", "")
    expected = request.cookies.get(CSRF_COOKIE, "")
    if not token or not expected or not secrets.compare_digest(str(token), expected):
        raise HTTPException(status_code=400, detail="Invalid or missing CSRF token")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(request: Request, template_name: str, context: dict | None = None,
           status_code: int = 200) -> HTMLResponse:
    context = dict(context or {})
    context.setdefault("request", request)
    context["current_user"] = getattr(request.state, "user", None)
    context["flash_messages"] = _decode_flash(request.cookies.get(FLASH_COOKIE))
    context["csrf_token"] = _ensure_csrf(request)
    context["url_for"] = lambda name, **kw: _build_url(request, name, **kw) if kw else str(request.url_for(name))
    context["qs"] = _qs
    context["static"] = _static
    context["app_name"] = settings.APP_NAME
    context["app_version"] = settings.APP_VERSION
    context["app_owner"] = settings.APP_OWNER
    context["copyright"] = settings.COPYRIGHT or f"Copyright \u00a9 {datetime.now().year} {settings.APP_OWNER}"

    response = templates.TemplateResponse(request, template_name, context)
    response.status_code = status_code

    if context["flash_messages"]:
        response.delete_cookie(FLASH_COOKIE, path="/")
    _set_cookie(response, CSRF_COOKIE, context["csrf_token"])
    return response


# --------------------------------------------------------------------------- #
# Session cookie issuance
# --------------------------------------------------------------------------- #
def issue_access_token(response, user: User) -> None:
    """Set the HTTP-only JWT cookie for an authenticated user."""
    response.set_cookie(
        "access_token",
        create_access_token(user.id, {"role": user.role}),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        path="/",
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
    )


# --------------------------------------------------------------------------- #
# Web authentication guards
# --------------------------------------------------------------------------- #
def get_current_user_web(request: Request) -> User:
    """Web dependency: redirect to /login when unauthenticated."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_admin_web(request: Request) -> User:
    """Web dependency: require admin role."""
    user = get_current_user_web(request)
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=302, headers={"Location": "/dashboard"})
    return user