# IPAM Manager

[![CI](https://github.com/rajeshprasanth/ipam-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/rajeshprasanth/ipam-manager/actions/workflows/ci.yml)

Enterprise IP Address Management (IPAM) built with FastAPI, SQLAlchemy,
PostgreSQL, and Bootstrap 5. Tracks IP addresses, networks, and devices with
role-based access control and a REST API.

## Repository

- Project page: <https://github.com/rajeshprasanth/ipam-manager>

## Features

- Enterprise landing page + dashboard with IP/network charts
- Role-based access control: `admin` (full) and `viewer` (read-only)
- Multiple sign-in options: local username/password, Google OAuth, GitHub OAuth
- Portal user management (create, edit, disable, reset passwords)
- Full REST API with JWT bearer auth
- PostgreSQL via SQLAlchemy + Alembic migrations (SQLite for local dev/tests)
- bcrypt password hashing, HTTP-only auth cookies, CSRF-protected forms
- MkDocs documentation site

## Quick start

```bash
git clone https://github.com/rajeshprasanth/ipam-manager.git
cd ipam-manager

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then set a strong SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

Create the first administrator (there is **no default account**):

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "admin"
```

Open <http://localhost:8000>. If you forget the admin password, re-run the same
command with the same username to reset it.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Documentation

Full docs are in [`docs/`](docs/) and built with MkDocs:

```bash
pip install -r requirements-dev.txt
mkdocs serve     # http://127.0.0.1:8000
```

## Deployment

Docker Compose with PostgreSQL 16:

```bash
docker compose -f Docker/docker-compose.yml up -d --build
```

See [Deployment](docs/deployment.md) for details and bare-metal instructions.

## Project layout

```
app/
  api/          # REST API routers
  web/          # Web portal routers (Jinja2)
  static/       # CSS / JS
  templates/    # Jinja2 templates
  config.py     # pydantic-settings configuration
  database.py   # SQLAlchemy engine/session
  models.py     # ORM models
  schemas.py    # Pydantic schemas
  security.py   # bcrypt + JWT
alembic/        # database migrations
docs/           # MkDocs site
tests/          # pytest suite (in-memory SQLite)
Docker/         # docker-compose
```

## License

[MIT](LICENSE)
