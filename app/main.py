"""FastAPI application entry point for the IPAM Manager."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.deps import extract_token, get_user_by_token
from app.web.deps import render

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenience for local development; production should rely on Alembic migrations.
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def attach_current_user(request: Request, call_next):
    """Resolve the authenticated user once per request and expose it on request.state."""
    request.state.user = None
    token = extract_token(request)
    if token:
        db = SessionLocal()
        try:
            request.state.user = get_user_by_token(db, token)
        finally:
            db.close()
    return await call_next(request)


# --------------------------------------------------------------------------- #
# REST API
# --------------------------------------------------------------------------- #
from app.api import auth as api_auth  # noqa: E402
from app.api import devices as api_devices  # noqa: E402
from app.api import ip_addresses as api_ip  # noqa: E402
from app.api import networks as api_networks  # noqa: E402
from app.api import stats as api_stats  # noqa: E402
from app.api import users as api_users  # noqa: E402

app.include_router(api_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(api_ip.router, prefix="/api/ip-addresses", tags=["ip-addresses"])
app.include_router(api_networks.router, prefix="/api/networks", tags=["networks"])
app.include_router(api_devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(api_users.router, prefix="/api/users", tags=["users"])
app.include_router(api_stats.router, prefix="/api", tags=["stats"])

# --------------------------------------------------------------------------- #
# Server-rendered portal
# --------------------------------------------------------------------------- #
from app.web import auth as web_auth  # noqa: E402
from app.web import dashboard as web_dashboard  # noqa: E402
from app.web import devices as web_devices  # noqa: E402
from app.web import ip_addresses as web_ip  # noqa: E402
from app.web import networks as web_networks  # noqa: E402
from app.web import oauth as web_oauth  # noqa: E402
from app.web import users as web_users  # noqa: E402

app.include_router(web_auth.router)
app.include_router(web_oauth.router)
app.include_router(web_dashboard.router)
app.include_router(web_ip.router)
app.include_router(web_networks.router)
app.include_router(web_devices.router)
app.include_router(web_users.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, _exc):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return render(request, "404.html", {}, status_code=404)