# Configuration

All configuration is read from environment variables or a `.env` file
(loaded via `pydantic-settings`, see `app/config.py`).

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `IPAM Manager` | Display name shown in the branding, page titles, and footers. |
| `APP_VERSION` | `1.0.0` | Version string shown in the footer. |
| `APP_OWNER` | `IPAM Manager Team` | Owner/company name displayed in portal footers. |
| `COPYRIGHT` | *(empty)* | Copyright line shown in footers. Leave empty to auto-generate `Copyright © <year> <APP_OWNER>`. |
| `DEBUG` | `false` | Enables debug behavior. Keep `false` in production. |
| `SECRET_KEY` | `change-me-in-production` | **Required in production.** Used to sign JWT, session, CSRF, and flash cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | JWT token lifetime in minutes (8 hours). |
| `DATABASE_URL` | `postgresql+psycopg2://ipam:ipam@localhost:5432/ipam` | SQLAlchemy connection string. See [Database & Migrations](database.md). |
| `COOKIE_SECURE` | `false` | Set to `true` when serving over **HTTPS** so auth cookies are only sent over TLS. |
| `COOKIE_SAMESITE` | `lax` | SameSite policy for cookies (`lax` / `strict` / `none`). |
| `GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID. When set together with the secret, "Continue with Google" appears on the login page. |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth client secret (never exposed to the browser). |
| `GITHUB_CLIENT_ID` | *(empty)* | GitHub OAuth client ID. |
| `GITHUB_CLIENT_SECRET` | *(empty)* | GitHub OAuth client secret. |
| `OAUTH_BASE_URL` | *(empty)* | Public base URL used to build OAuth redirect callbacks. Empty ⇒ derived from the request `Host` header. Set explicitly when behind a proxy / HTTPS (e.g. `https://ipam.example.com`). |
| `AUTO_CREATE_TABLES` | `true` | Creates tables on startup — dev convenience. Use `false` in production and rely on Alembic migrations. |

## Example `.env`

```dotenv
APP_NAME=IPAM Manager
APP_VERSION=1.0.0
DEBUG=false

SECRET_KEY=<64-char-random-string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

DATABASE_URL=postgresql+psycopg2://ipam:ipam@localhost:5432/ipam

COOKIE_SECURE=true
COOKIE_SAMESITE=lax

AUTO_CREATE_TABLES=false
```

!!! warning "Never commit a real `.env`"
    `.env` is ignored by git. Keep only `.env.example` in the repository.

## SQLite URLs (local dev / tests)

SQLite is automatically detected and configured with a `StaticPool` and
check-same-thread disabled, e.g.:

```dotenv
DATABASE_URL=sqlite:///./ipam.db
```