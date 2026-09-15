"""Application configuration loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    DATABASE_URL: str = "postgresql+psycopg2://ipam:ipam@localhost:5432/ipam"

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