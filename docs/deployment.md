# Deployment

## Docker Compose (recommended)

The project ships a Compose stack with **PostgreSQL 16** and the web app
(run via Gunicorn + Uvicorn workers; Alembic migrations applied at startup).

```bash
docker compose -f Docker/docker-compose.yml up -d --build
```

- Web app: `http://localhost:8000`
- PostgreSQL: `localhost:5432` (user/password/database all `ipam`)

### Environment overrides

Before first boot, edit `SECRET_KEY` in `Docker/docker-compose.yml`:

```yaml
SECRET_KEY: <64-char-random-string>
COOKIE_SECURE: "true"
```

Then create the first admin:

```bash
docker exec -it ipam-manager python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

(note: the base image is `python:3.12-slim`; the exact `python` used to install
deps is available in the container).

### Data & logs

- Database data lives in the named volume `pgdata` (survives container rebuilds).
- `./Docker/logs` is mounted into the container for application logs.

## Bare-metal / VM

1. Create a PostgreSQL database and user.
2. Set environment variables (copy `.env.example` → `.env`, set a real `SECRET_KEY`).
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `python -m app.scripts.create_admin ...`
6. Run with Gunicorn:

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

7. Put a reverse proxy (nginx / Caddy / Traefik) in front with TLS, set
   `COOKIE_SECURE=true`.

## Homepage / documentation site

The documentation is built with **MkDocs** (Material theme). To build locally:

```bash
pip install -r requirements-dev.txt
mkdocs build          # outputs to site/
mkdocs serve          # http://127.0.0.1:8000
```

Builds are reproducible from any checkout since the doc files and `mkdocs.yml`
live in the repository.

## Backup & restore

See [Database & Migrations → Backups](database.md#backups-postgresql).