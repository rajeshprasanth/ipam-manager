# Deployment

## Quick start (one script)

```bash
./install.sh            # interactive — choose Docker Compose, host+PostgreSQL, or host+SQLite
./install.sh <mode>     # non-interactive: docker | host-postgres | host-sqlite
```

`./install.sh start` starts the app detached; `./install.sh stop` stops it;
`./install.sh status` reports where it is running and where the logs are.
See [Getting Started](getting-started.md) for the full command list.

## Docker Compose (recommended)

The project ships a Compose stack with **PostgreSQL 16** and the web app
(run via Gunicorn + Uvicorn workers; Alembic migrations applied at startup).
`DATABASE_URL` is built by `app/config.py` from `POSTGRES_HOST` + `POSTGRES_*`:
the Compose file pins `POSTGRES_HOST=db` so the container always talks to the
bundled database (no hostname guessing); on the host it falls back to
`localhost`. Set an explicit `DATABASE_URL` only for a remote/managed database.

```bash
docker compose -f Docker/docker-compose.yml up -d --build
```

- Web app: `http://localhost:8076` (see `APP_PORT` in `.env`)
- PostgreSQL: `localhost:5432` (user/password/database all `ipam`)
- Containers are named `IPAM-Manager-Web` and `IPAM-Manager-DB`

The Build context is the repository root (`context: ..`), so the stack can be
started from anywhere with `-f Docker/docker-compose.yml`. Variables are read
from your `.env` via environment export — the Compose file interpolates
`${APP_PORT}`, `${POSTGRES_*}`, `${SECRET_KEY}`, etc. from it.

### Environment overrides

Before first boot, make sure `SECRET_KEY` is set (in `.env` or the
environment). Use `./install.sh docker` to generate everything interactively:

```dotenv
SECRET_KEY=<64-char-random-string>
COOKIE_SECURE=true
```

### First admin

```bash
./install.sh admin
# or into the running web container:
docker exec -it IPAM-Manager-Web python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

### Data & logs

- Database data lives in the named volume `pgdata` (survives container rebuilds
  and `down`; removed by `./install.sh uninstall` / `down -v`).
- App **and** PostgreSQL logs are written to `./logs` on the host, bind-mounted
  into both containers (`:Z` handles SELinux-enforcing hosts such as Fedora):

  | Container    | Mounted at       | Files                               |
  |--------------|------------------|-------------------------------------|
  | `IPAM-Manager-Web` | `/var/log/ipam`  | `gunicorn-access.log`, `gunicorn-error.log` |
  | `IPAM-Manager-DB`  | `/var/log/postgres` | `postgresql-YYYY-MM-DD_HHMMSS.log` |

- At startup each container **fixes directory permissions itself** (works even
  when Compose created `./logs` as root-owned), then drops back to its
  unprivileged user (`app` / `postgres`). No manual `chmod` needed.
- PostgreSQL rotates its own logs (`log_rotation_age=1d`,
  `log_rotation_size=100MB`); host logs are managed by logrotate/gunicorn.

!!! note "`docker compose logs`"
    Because gunicorn writes to files (not stdout), `docker compose logs -f web`
    shows only entrypoint output (wait-for-db, alembic, "starting gunicorn").
    The full access/error logs are in `./logs/gunicorn-*.log`.

## Bare-metal / VM

The `host-postgres` / `host-sqlite` installer options do everything for you
(venv, deps, database bootstrap, admin, detached gunicorn):

```bash
./install.sh host-postgres
```

Manually:

1. Create a PostgreSQL database and user.
2. Set environment variables (copy `.env.example` → `.env`, set a real `SECRET_KEY`).
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `python -m app.scripts.create_admin ...`
6. Run with Gunicorn:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8076
```

7. Put a reverse proxy (nginx / Caddy / Traefik) in front with TLS, set
   `COOKIE_SECURE=true`.

## Homepage / documentation site

The documentation is built with **MkDocs** (Material theme):

```bash
./install.sh docs         # install deps + serve at 127.0.0.1:${DOCS_PORT} (default 8000)
./install.sh docs-build   # strict build into site/
```

Manual equivalent:

```bash
pip install -r requirements-docs.txt
mkdocs serve --dev-addr 127.0.0.1:8000
mkdocs build --strict     # outputs to site/
```

Builds are reproducible from any checkout since the doc files and `mkdocs.yml`
live in the repository.

## Backup & restore

See [Database & Migrations → Backups](database.md#backups-postgresql).