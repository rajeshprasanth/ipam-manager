#!/bin/sh
set -e

# Run as root initially (so we can fix bind-mounted log permissions), then
# drop to the unprivileged "app" user before starting gunicorn.
RUN_AS="setpriv --reuid app --regid app --init-groups"

: "${SECRET_KEY:?SECRET_KEY must be set}"

# DATABASE_URL is optional: app/config.py builds it from POSTGRES_* and
# POSTGRES_HOST (pinned to "db" by docker-compose.yml) and honours an
# explicitly set DATABASE_URL. When either is set, we wait for that database
# before running migrations.

if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_HOST" ]; then
    # --------------------------------------------------------------------------- #
    # Wait for the database to become reachable (Postgres can be slower than the
    # app container on cold starts).
    # --------------------------------------------------------------------------- #
    echo "[entrypoint] waiting for database..."
    python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
else:
    user = os.environ.get("POSTGRES_USER", "ipam")
    password = os.environ.get("POSTGRES_PASSWORD", "ipam")
    db = os.environ.get("POSTGRES_DB", "ipam")
    host = os.environ["POSTGRES_HOST"]
    engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:5432/{db}")
try:
    for attempt in range(30):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[entrypoint] database is reachable")
            break
        except Exception as exc:
            print(f"[entrypoint] db not ready ({attempt + 1}/30): {exc.__class__.__name__}", flush=True)
            time.sleep(2)
    else:
        print("[entrypoint] could not reach the database", flush=True)
        print(f"[entrypoint] is the database container running and on the same network as this container?", flush=True)
        print("[entrypoint]   docker compose -f Docker/docker-compose.yml ps", flush=True)
        print("[entrypoint]   docker exec <this-container> getent hosts db", flush=True)
        print("[entrypoint] for standalone runs set DATABASE_URL (and unset POSTGRES_HOST)", flush=True)
        raise SystemExit(1)
finally:
    engine.dispose()
PY
else
    echo "[entrypoint] DATABASE_URL / POSTGRES_HOST not set — the app will use its default of postgres://ipam:ipam@localhost:5432/ipam"
    echo "[entrypoint] tip: when running this image outside docker-compose, set DATABASE_URL to your database"
fi

# --------------------------------------------------------------------------- #
# Apply schema migrations before accepting traffic.
# --------------------------------------------------------------------------- #
echo "[entrypoint] running alembic migrations..."
alembic upgrade head

# --------------------------------------------------------------------------- #
# Start the server. PORT is injected by container platforms (Render, etc.);
# GUNICORN_WORKERS defaults to 2 (safe for small instances).
# LOG_DIR (optional) points gunicorn's access/error logs at files, so they
# accumulate on a mounted host folder; when unset, logs go to stdout/stderr
# (captured by `docker compose logs`).
# --------------------------------------------------------------------------- #
echo "[entrypoint] starting gunicorn (${GUNICORN_WORKERS:-2} workers)..."
ACCESS_LOG="-"
ERROR_LOG="-"
if [ -n "${LOG_DIR:-}" ]; then
    mkdir -p "$LOG_DIR"
    # Compose may have created the host logs/ directory as root:0755 — make it
    # world-writable so the unprivileged gunicorn user can write its files.
    chmod 777 "$LOG_DIR" 2>/dev/null || true
    ACCESS_LOG="$LOG_DIR/gunicorn-access.log"
    ERROR_LOG="$LOG_DIR/gunicorn-error.log"
    echo "[entrypoint] writing logs to $LOG_DIR/"
fi
exec $RUN_AS gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -b "0.0.0.0:${PORT:-8076}" \
    -w "${GUNICORN_WORKERS:-2}" \
    --timeout 60 \
    --graceful-timeout 30 \
    --access-logfile "$ACCESS_LOG" \
    --error-logfile "$ERROR_LOG"