# IPAM Manager

**Enterprise IP Address Management (IPAM)** — a production-grade web portal and
REST API for tracking IP addresses, networks, and devices. Built with **FastAPI,
SQLAlchemy, PostgreSQL, and Bootstrap 5**, with role-based access control and
multiple sign-in options.

- **Project page:** <https://github.com/rajeshprasanth/ipam-manager>
- Interactive API docs: `/api/docs` (OpenAPI / Swagger UI)

---

## Table of contents

1. [Features](#features)
2. [Tech stack](#tech-stack)
3. [Project layout](#project-layout)
4. [Quick start](#quick-start)
5. [Configuration](#configuration)
6. [First administrator](#first-administrator)
7. [Authentication & RBAC](#authentication--rbac)
8. [REST API](#rest-api)
9. [Database & migrations](#database--migrations)
10. [Running tests](#running-tests)
11. [Documentation site](#documentation-site)
12. [Deployment](#deployment)
13. [Troubleshooting](#troubleshooting)
14. [License](#license)

---

## Features

- **Enterprise landing page** with a feature/security overview and CTA.
- **Dashboard** with network/device/IP statistics and Chart.js visualizations.
- **IP, network, and device inventory** — full CRUD from the portal with
  search, filtering, and pagination; every IP change is recorded in an audit
  history.
- **Role-based access control** — `admin` (full control) and `viewer`
  (read-only), enforced in both the web UI and the REST API.
- **Multiple sign-in options** — local username/password, **Google OAuth**, and
  **GitHub OAuth**.
- **User management** — admins can create, edit, disable, delete, and reset
  passwords for portal users (with self-lockout protection).
- **REST API** — JSON API with JWT bearer authentication for scripts and
  integrations.
- **Real database** — PostgreSQL in production via SQLAlchemy + Alembic
  migrations; SQLite for local development and the test suite.
- **Security defaults** — bcrypt password hashing, HTTP-only JWT cookies,
  per-form CSRF protection, signed flash messages, state-guarded OAuth
  callbacks.
- **Configurable branding** — project name, owner, and copyright pulled from
  environment variables.

## Tech stack

| Component  | Choice                                             |
|------------|----------------------------------------------------|
| Framework  | FastAPI (async, OpenAPI out of the box)            |
| Templates  | Jinja2 + Bootstrap 5 + Chart.js                    |
| ORM        | SQLAlchemy 2.x                                     |
| Migrations | Alembic                                            |
| Database   | PostgreSQL 16 (dev: SQLite)                        |
| Auth       | bcrypt + JWT (python-jose) + OAuth 2.0 (Google/GitHub) |
| HTTP       | httpx (server-side OAuth exchange)                 |
| Server     | Uvicorn (dev) / Gunicorn + Uvicorn workers (prod)  |
| Docs       | MkDocs + Material for MkDocs                       |

## Project layout

```
ipam-manager/
├── app/
│   ├── api/            # REST API routers (auth, users, ip/networks/devices, stats)
│   ├── web/            # Server-rendered portal routers (Jinja2)
│   │   ├── oauth.py    # Google / GitHub OAuth 2.0 flow
│   │   └── deps.py     # render / flash / CSRF / url helpers, web guards
│   ├── static/         # app.css, app.js
│   ├── templates/      # Jinja2 templates + partials
│   ├── scripts/        # create_admin.py (bootstrap / reset admin)
│   ├── config.py       # pydantic-settings configuration (env / .env)
│   ├── database.py     # SQLAlchemy engine + session
│   ├── models.py       # ORM models
│   ├── schemas.py      # Pydantic schemas + validators
│   ├── security.py     # bcrypt hashing + JWT helpers
│   └── main.py         # FastAPI app assembly
├── alembic/            # database migrations (versions/0001_initial.py)
├── docs/               # MkDocs documentation source
├── tests/              # pytest suite (in-memory SQLite)
├── Docker/             # docker-compose (postgres:16 + app)
├── Dockerfile
├── mkdocs.yml
├── requirements.txt    # pinned runtime dependencies
├── requirements-dev.txt
└── .env.example        # configuration template
```

## Quick start

### Prerequisites

- Python **3.10+** (developed against 3.12/3.13/3.14)
- (Optional, for production) PostgreSQL 16

### 1. Clone and install

```bash
git clone https://github.com/rajeshprasanth/ipam-manager.git
cd ipam-manager

python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

pip install -r requirements.txt      # runtime deps
pip install -r requirements-dev.txt  # + tests + docs
```

### 2. Configure

```bash
cp .env.example .env
```

Generate a strong secret and put it in `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`AUTO_CREATE_TABLES=true` creates the tables on startup for local development
(SQLite is used automatically when `DATABASE_URL` is a `sqlite://` URL). For
PostgreSQL, set:

```dotenv
DATABASE_URL=postgresql+psycopg2://ipam:ipam@localhost:5432/ipam
```

### 3. Bootstrap the first administrator

There is **no default account**. Create one:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

### 4. Run

```bash
uvicorn app.main:app --reload --port 8000
```

| URL                          | What you'll see                     |
|------------------------------|-------------------------------------|
| `http://localhost:8000/`      | Enterprise landing page            |
| `http://localhost:8000/login` | Sign-in (local + optional OAuth)   |
| `http://localhost:8000/dashboard` | Dashboard with stats         |
| `http://localhost:8000/api/docs` | Interactive API documentation |

## Configuration

All settings are read from environment variables or a `.env` file
(`app/config.py`). `.env` is git-ignored — never commit it.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `IPAM Manager` | Brand name shown in titles, nav, and footers. |
| `APP_VERSION` | `1.0.0` | Version string in the portal footer. |
| `APP_OWNER` | `IPAM Manager Team` | Owner/company name in portal footers. |
| `COPYRIGHT` | *(auto)* | Copyright line; defaults to `Copyright © <year> <APP_OWNER>`. |
| `DEBUG` | `false` | Debug mode. Keep `false` in production. |
| `SECRET_KEY` | `change-me-in-production` | **Change in production.** Signs JWT, CSRF, and flash cookies. |
| `ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Session/JWT lifetime (8 hours). |
| `DATABASE_URL` | `postgresql+psycopg2://ipam:ipam@localhost:5432/ipam` | SQLAlchemy URL. |
| `COOKIE_SECURE` | `false` | `true` over HTTPS so cookies are TLS-only. |
| `COOKIE_SAMESITE` | `lax` | Cookie SameSite policy. |
| `GOOGLE_CLIENT_ID` | *(empty)* | Enable "Continue with Google". |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth secret (server-only). |
| `GITHUB_CLIENT_ID` | *(empty)* | Enable "Continue with GitHub". |
| `GITHUB_CLIENT_SECRET` | *(empty)* | GitHub OAuth secret (server-only). |
| `OAUTH_BASE_URL` | *(empty)* | Public base URL for OAuth callbacks; defaults to the request `Host` header. |
| `AUTO_CREATE_TABLES` | `true` | Create tables on startup (dev). Set `false` in production and use `alembic upgrade head`. |

## First administrator

Bootstrapping, and **password recovery**, use the same idempotent script.
Re-running it with an existing username resets the password, forces the `admin`
role, and re-activates the account:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-new-strong-password"
```

## Authentication & RBAC

### Roles

| Role     | Web portal                                  | REST API                     |
|----------|---------------------------------------------|------------------------------|
| `admin`  | Full CRUD + user management                 | Full CRUD + user management  |
| `viewer` | Read-only pages (no add/edit/delete)        | Read endpoints only (`403` on writes) |

### Local login

Passwords are stored as **bcrypt** hashes. On login the server issues a **JWT**,
stored in an **HTTP-only** `access_token` cookie. Web guards redirect
unauthenticated users to `/login` and non-admins away from admin pages.

### OAuth (Google / GitHub)

- The provider buttons appear on the login page only when both the client id
  and secret for that provider are configured.
- Standard **authorization-code flow**: handoff → provider consent →
  server-side token exchange → verified-email lookup/provisioning.
- Callbacks are CSRF-protected with a random `state` parameter (signed
  `oauth_state_<provider>` cookie); provider secrets never reach the browser.
- Accounts are matched by **verified email**. If no local user matches, one is
  auto-provisioned with the `viewer` role. OAuth-created accounts have no local
  password (grant one via **Users → reset password**).
- Callback URLs (register these with the providers, under
  `OAUTH_BASE_URL` or your public origin):
  - Google: `/auth/callback/google`
  - GitHub: `/auth/callback/github`

### Guards & CSRF

- `get_current_user_web` / `require_admin_web` — portal redirects.
- `get_current_user_api` / `require_admin_api` — API `401`/`403`.
- Every mutating portal form must include a `_csrf` token (checked against the
  `ipam_csrf` cookie) or the request is rejected with `400`.

## REST API

Base URL `/api` — interactive specs at `/api/docs`. All endpoints (except
login) require:

```
Authorization: Bearer <access_token>
```

`**A**` = admin only, `**V**` = any authenticated role (read-only).

### Auth

| Method | Path                | Role | Description              |
|--------|---------------------|------|--------------------------|
| POST   | `/api/auth/login`   | —    | Obtain a JWT             |
| GET    | `/api/auth/me`      | V    | Current user             |

### Users

| Method | Path                                   | Role | Description                |
|--------|----------------------------------------|------|----------------------------|
| GET    | `/api/users`                           | A    | List users                 |
| GET    | `/api/users/{id}`                      | A    | Get one                    |
| POST   | `/api/users`                           | A    | Create user                |
| PATCH  | `/api/users/{id}`                      | A    | Update (role, active, …)   |
| DELETE | `/api/users/{id}`                      | A    | Delete                     |
| POST   | `/api/users/{id}/reset-password`       | A    | Reset password             |

### IP addresses

| Method | Path                                  | Role | Description                     |
|--------|---------------------------------------|------|---------------------------------|
| GET    | `/api/ip-addresses`                   | V    | List (search/status/page)       |
| GET    | `/api/ip-addresses/{id}`              | V    | Get one                         |
| POST   | `/api/ip-addresses`                   | A    | Create (`409` on duplicate IP)  |
| PATCH  | `/api/ip-addresses/{id}`              | A    | Update                          |
| DELETE | `/api/ip-addresses/{id}`              | A    | Delete                          |

### Networks & devices

| Method | Path                     | Role | Description    |
|--------|--------------------------|------|----------------|
| GET    | `/api/networks`, `/api/networks/{id}`        | V    | List / get     |
| POST   | `/api/networks`          | A    | Create         |
| PATCH  | `/api/networks/{id}`     | A    | Update         |
| DELETE | `/api/networks/{id}`     | A    | Delete         |
| GET    | `/api/devices`, `/api/devices/{id}`          | V    | List / get     |
| POST   | `/api/devices`           | A    | Create         |
| PATCH  | `/api/devices/{id}`      | A    | Update         |
| DELETE | `/api/devices/{id}`      | A    | Delete         |

### Stats

`GET /api/stats` → totals plus a per-status breakdown of IP addresses.

### Error codes

`401` missing/invalid token · `403` insufficient role / disabled ·
`404` not found · `409` conflict (duplicate IP/user) · `422` validation ·
`204` successful delete.

## Database & migrations

Models: `User`, `IPAddress`, `Network`, `Device`, `IPHistory` (audit log).

```bash
alembic upgrade head        # apply migrations
alembic revision --autogenerate -m "describe change"   # new migration
alembic downgrade -1        # rollback one step
```

Backup / restore (PostgreSQL):

```bash
pg_dump -U ipam -h localhost ipam > ipam-$(date +%F).sql
psql -U ipam -h localhost ipam < ipam-YYYY-MM-DD.sql
```

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite (23 tests) runs against an in-memory SQLite database with no external
services. It covers portal auth & RBAC, API CRUD and role guards, CSRF, and the
Google/GitHub OAuth flows (provider HTTP calls faked).

## Documentation site

Full MkDocs documentation lives in `docs/`:

```bash
pip install -r requirements-dev.txt
mkdocs serve     # http://127.0.0.1:8000
mkdocs build     # outputs static site/ directory
```

## Deployment

### Docker Compose (recommended)

Brings up PostgreSQL 16 and the app (Gunicorn + Uvicorn workers, Alembic
applied on boot):

```bash
docker compose -f Docker/docker-compose.yml up -d --build
```

- App: `http://localhost:8000`
- Default DB in the compose stack: `ipam` / `ipam` (user/password/database)

**Before first boot**, set a real `SECRET_KEY` (and optionally OAuth client
credentials) in `Docker/docker-compose.yml`, then seed the admin:

```bash
docker exec -it ipam-manager python -m app.scripts.create_admin \
    --username admin --email admin@example.com --password "a-strong-password"
```

### Bare-metal / VM

1. Create the PostgreSQL database and user.
2. Copy `.env.example` → `.env`, set a real `SECRET_KEY` (and `DATABASE_URL`).
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `python -m app.scripts.create_admin ...`
6. Serve with Gunicorn:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

7. Terminate TLS at nginx/Caddy/Traefik and set `COOKIE_SECURE=true` plus
   `OAUTH_BASE_URL=https://your-public-host` if using OAuth.

> **CI/CD note:** the `.github/workflows/ci.yml` GitHub Actions workflow is
> currently disabled (untracked) so the repository can be pushed with a token
> that lacks `workflow` scope. To re-enable it, see the `.gitignore` note and
> re-add the file.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No default credentials" | There are none — run `create_admin` first. |
| Forgot the admin password | Re-run `create_admin` with the same username — it resets the password and re-promotes the account. |
| Social buttons missing | Set both the client id **and** secret for that provider, then restart. |
| OAuth `redirect_uri_mismatch` | Register `<public-origin>/auth/callback/<provider>` exactly; set `OAUTH_BASE_URL` behind a proxy. |
| OAuth user is not an admin | OAuth-provisioned accounts start as `viewer` — promote via **Users**. |
| Port 8000 already in use | Stop the stale server or change the port: `uvicorn app.main:app --port 8001`. |

## License

[MIT](LICENSE) — Copyright (c) 2026 IPAM Manager Team.