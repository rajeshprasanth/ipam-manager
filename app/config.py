"""Application configuration loaded from environment / .env file."""
import os
import socket
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Populate os.environ from .env so bare-metal runs can feed POSTGRES_* /
# APP_PORT etc. into default value helpers below (idempotent in containers,
# where env vars are provided out-of-band).
load_dotenv()


def _resolve_db_host() -> str:
    """Return the PostgreSQL host that fits the current runtime.

    Precedence:
      1. ``POSTGRES_HOST`` (the Compose file pins this to ``db`` so the
         container never guesses).
      2. The ``db`` hostname on a Docker Compose network.
      3. ``localhost`` (bare-metal / VM / Render with DATABASE_URL set).
    """
    explicit = os.environ.get("POSTGRES_HOST")
    if explicit:
        return explicit
    try:
        socket.getaddrinfo("db", 5432, socket.AF_INET)
        return "db"
    except socket.gaierror:
        pass
    try:
        socket.getaddrinfo("db", 5432, socket.AF_INET6)
        return "db"
    except socket.gaierror:
        pass
    return "localhost"


def _default_db_url() -> str:
    """Build the default DATABASE_URL when none is provided."""
    user = os.environ.get("POSTGRES_USER", "ipam")
    password = os.environ.get("POSTGRES_PASSWORD", "ipam")
    db = os.environ.get("POSTGRES_DB", "ipam")
    return f"postgresql+psycopg2://{user}:{password}@{_resolve_db_host()}:5432/{db}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "IPAM Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Owner / copyright metadata rendered in portal footers.
    # If COPYRIGHT is empty it defaults to "Copyright © <year> APP_OWNER".
    APP_OWNER: str = "IPAM Manager Team"
    COPYRIGHT: str = ""

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Auto-detected: "db" inside a Docker network, "localhost" elsewhere.
    # An explicit DATABASE_URL always takes precedence over this default.
    DATABASE_URL: str = _default_db_url()

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # OAuth / social sign-in. A provider is enabled only when both
    # client_id and client_secret are set.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Public base URL used to build OAuth redirect_uri callbacks.
    # Leave empty to derive from the incoming request's Host header
    # (set it explicitly when the app sits behind a proxy/HTTPS).
    OAUTH_BASE_URL: str = ""

    AUTO_CREATE_TABLES: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()