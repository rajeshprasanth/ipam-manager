# IPAM Manager

**Enterprise IP Address Management (IPAM) — a production-grade FastAPI application.**

IPAM Manager tracks IP addresses, networks, and devices with role-based access
control (admin / view-only), a modern Bootstrap 5 web portal, and a REST API.

## Features

- **Web portal** with an enterprise landing page, dashboard with network/IP charts, and list/CRUD pages for IP addresses, networks, and devices.
- **Role-based access control** — `admin` (full control) and `viewer` (read-only), enforced in both the web UI and the REST API.
- **User management** — admins can create, edit, disable, and reset passwords for portal users from a dedicated page.
- **REST API** — JSON API with JWT bearer authentication for scripts and integrations.
- **Real database** — PostgreSQL in production (via SQLAlchemy + Alembic migrations); SQLite supported for local development and tests.
- **Hardened auth** — bcrypt password hashing, HTTP-only JWT cookies, per-form CSRF protection, signed flash messages.
- **One-script installer** — interactive setup and a management menu (Docker Compose / host + PostgreSQL / host + SQLite), detached start/stop, and file-based logs in `./logs` for both container and host installs.

## Tech stack

| Component  | Choice                                   |
|------------|------------------------------------------|
| Framework  | FastAPI                                  |
| Templates  | Jinja2 + Bootstrap 5                     |
| ORM        | SQLAlchemy 2.x                           |
| Migrations | Alembic                                  |
| Database   | PostgreSQL 16 (dev: SQLite)              |
| Auth       | bcrypt + JWT (python-jose)               |
| Server     | Uvicorn (dev) / Gunicorn + Uvicorn (prod)|

## Quick start

```bash
./install.sh      # interactive installer + management menu
```

See [Getting Started](getting-started.md) for details and the non-interactive
commands (`docker`, `host-postgres`, `host-sqlite`, `start`, `stop`, `docs`, …).

## Documentation

- [Getting Started](getting-started.md) — install, run, and create your first admin.
- [Configuration](configuration.md) — environment variables.
- [Database & Migrations](database.md) — models, Alembic, backups.
- [Security & RBAC](security.md) — authentication, roles, CSRF.
- [User Management](user-management.md) — managing administrator accounts.
- [REST API](api.md) — endpoints reference.
- [Deployment](deployment.md) — Docker Compose with PostgreSQL.
- [Troubleshooting & FAQ](troubleshooting.md) — password recovery, common issues.

## License

[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html) —
Copyright (c) 2026 IPAM Manager Team.