# Getting Started

## Requirements

- Python **3.10+** (developed and tested on 3.12)
- PostgreSQL 16 for production (optional for local dev)
- Docker + Docker Compose plugin for the container install
- `setpriv` (util-linux) for the container install — present on Debian/Ubuntu derivatives

## Recommended: one-script installer

`./install.sh` is an interactive installer **and** runtime manager. Run it
from the repository root:

```bash
./install.sh
```

It asks you for:

- the application name, owner, and **web UI port** (default `8076`),
- a `SECRET_KEY` (generate one automatically or paste your own),
- the **database backend** — Docker Compose, host + PostgreSQL, or host + SQLite,
- the **MkDocs port** for the local documentation site (default `8000`),
- an **admin account** (username / email / password).

Then it installs dependencies into `.venv`, builds/starts the chosen stack,
and drops you into a management menu:

| Option | Action |
|--------|--------|
| `1` | Install & run — Docker Compose (PostgreSQL + app) |
| `2` | Install — this host with PostgreSQL |
| `3` | Install — this host with SQLite (quick dev) |
| `4` | Create / reset an admin account |
| `5` | Run database migrations (alembic) |
| `6` | Start the app (detached, logs → `./logs`) |
| `7` | Stop the app / stack |
| `8` | Status |
| `9` | Uninstall |
| `d` / `b` | Serve / build the MkDocs documentation |

Everything can be driven non-interactively too:

```bash
./install.sh docker                # container mode (env vars / defaults)
./install.sh host-postgres         # host + PostgreSQL
./install.sh host-sqlite           # host + SQLite (quick dev)
./install.sh check                 # environment diagnostics
./install.sh start                 # start the app detached
./install.sh stop                  # stop the app / stack
./install.sh status                # where the app is, PID/container, logs
./install.sh docs                  # serve MkDocs at 127.0.0.1:${DOCS_PORT}
./install.sh docs-build            # build static site into ./site
./install.sh admin                 # create / reset an admin account
./install.sh migrate               # alembic upgrade head
./install.sh uninstall             # remove containers / venv
```

Settings are persisted in `.env` (see [Configuration](configuration.md)).

## Manual alternative

If you prefer to do it by hand:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

At minimum set a strong `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Then put the output into `SECRET_KEY` in `.env`.

For local development the default SQLite database works out of the box
(`AUTO_CREATE_TABLES=true` creates tables on startup). For PostgreSQL on the
host, set:

```dotenv
DATABASE_URL=postgresql+psycopg2://ipam:ipam@localhost:5432/ipam
```

In the Docker stack you usually do **not** set `DATABASE_URL` at all — the app
auto-detects the `db` service (see [Deployment](deployment.md)).

## Create the first administrator

There is **no default username or password**. Bootstrap the first admin:

```bash
./install.sh admin
```

or directly:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

If `--password` is omitted you will be prompted interactively.

!!! note "Idempotent & recoverable"
    Re-running the script with the same username **does not fail** — it updates
    the existing account: resets the password, forces the role to `admin`, and
    re-activates it. This is also your password-recovery path (see
    [Troubleshooting](troubleshooting.md)).

## Run it

Detached with logs in `./logs` (persists across reboots):

```bash
./install.sh start
./install.sh status
./install.sh stop
```

Foreground / development:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8076
# or
python run.py
```

## Verify

| URL                                   | What to check                                  |
|---------------------------------------|------------------------------------------------|
| `http://localhost:8076/`              | Enterprise landing page                  |
| `http://localhost:8076/login`         | Sign in with your new admin credentials  |
| `http://localhost:8076/dashboard`     | Dashboard with IP / network stats   |
| `http://localhost:8076/docs`          | FastAPI auto-generated OpenAPI docs     |

## Logs

Application logs accumulate in `./logs` for **both** Docker and host installs:

| Source      | File(s)                              |
|-------------|--------------------------------------|
| Host mode   | `ipam-access.log`, `ipam-app.log`    |
| Docker app  | `gunicorn-access.log`, `gunicorn-error.log` |
| PostgreSQL  | `postgresql-YYYY-MM-DD_HHMMSS.log`   |

The `./logs` directory is auto-created with the right permissions; Docker
containers also self-fix the mount at startup and then drop back to an
unprivileged user. See [Deployment → Data & logs](deployment.md#data-logs).

## Optional: enable social sign-in

Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` (and/or `GITHUB_CLIENT_ID` +
`GITHUB_CLIENT_SECRET`) in `.env`, plus `OAUTH_BASE_URL` if behind a proxy.
"Continue with Google / GitHub" buttons then appear on the login page. See
[Security & RBAC → OAuth](security.md#oauth-social-sign-in-google-github).

## Run the test suite

```bash
pytest
```

The suite uses an in-memory SQLite database and needs no external services.
It seeds `admin` and `viewer` test accounts automatically (see `tests/conftest.py`).