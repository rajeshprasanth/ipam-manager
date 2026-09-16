# Troubleshooting & FAQ

## "Could not translate host name 'db' to address" or "connection to server at localhost ... refused"

Both mean the **web container cannot reach a running database**. They are two
symptoms of the same problem; which one you see depends on how `POSTGRES_HOST`
is set:

- `db` does not resolve → the database container is **not running** or the web
  container is **not on the same Docker network** as it.
- falls back to `localhost` (refused) → the web container is running as a
  standalone container with no database next to it.

Diagnose:

```bash
docker compose -f Docker/docker-compose.yml ps          # are BOTH services Up?
docker ps                                                # is there a db container?
docker network ls                                        # same network? (default is ipam-manager_default)
docker exec IPAM-Manager-Web getent hosts db             # empty = db unknown to web
docker logs IPAM-Manager-DB                              # any errors in the DB?
```

Fixes:

- Prefer the whole stack: `docker compose -f Docker/docker-compose.yml up -d --build`.
- If running the app image **standalone** (no `db` service), the container has
  no database at all — you must point it at one:
  `docker run ... -e DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB ...`
  (or run it on the same custom network as a Postgres container whose alias is
  `db`).
- After `docker compose down`, the network is removed — start it again with
  `up -d` (never `docker start IPAM-Manager-Web` alone).

## First admin / password recovery

**There is no default account.** Create (or reset) the administrator with:

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

In the Docker stack, run it inside the web container:

```bash
docker exec -it IPAM-Manager-Web python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-new-strong-password"
```

Running it again **with the same username** resets the password, restores the
`admin` role, and re-activates the account — this is your recovery mechanism.

!!! tip "This is your recovery mechanism"
    There is intentionally no "forgot password" email flow. Keep a copy of the
    script and the server shell access available for emergencies.

## I'm an admin but I can't demote/disable a user

By design you cannot:

- Demote, disable, or delete **your own account**.
- Demote/disable the **last active administrator** (protects against locking
  everyone out).

## A viewer can't see the "Add" buttons

Correct — viewers are read-only. Management buttons are only rendered for
`admin` users (and the API returns `403` for viewer writes).

## Is session state / flash broken behind a proxy?

If flash messages intermittently fail, ensure cookies are configured correctly
for your proxy domain, and that `COOKIE_SAMESITE`/`COOKIE_SECURE` match your
deployment (see [Configuration](configuration.md)).

## The app works but asks for a database at startup

Set `AUTO_CREATE_TABLES=true` only for local dev, or run `alembic upgrade head`
against your `DATABASE_URL` for production (see [Database](database.md)).

## Why do my tests use SQLite while prod uses Postgres?

The test suite (`tests/conftest.py`) uses in-memory SQLite for speed and zero
setup. Only SQLAlchemy-standard features are used so behavior matches. Run the
suite locally with `pytest`.

## I don't see the "Continue with Google / GitHub" buttons

Providers only appear when the matching `*_CLIENT_ID` **and** `*_CLIENT_SECRET`
are both set in the environment (see [Configuration](configuration.md)). Restart
the app after changing them.

## "redirect_uri_mismatch" / "The redirect_uri in the request does not match"

The provider's recorded callback URL must exactly equal
`<public_base_url>/auth/callback/<provider>`. Either register that exact URL on
the provider console, or set `OAUTH_BASE_URL` in `.env` to the exact public
origin behind your proxy. If `COOKIE_SECURE=true`, the public URL must be HTTPS.

## My OAuth sign-in works but the user has no admin rights

OAuth-provisioned accounts start as `viewer`. Promote the user to `admin` from
**Users**, or bootstrap a local admin with `create_admin`.

## A user says their social account no longer signs them in

Accounts are matched by verified email. If the provider email changed, create
the account again (or update the user's email in the portal). OAuth accounts
have no local password — use **Users → reset password** to grant one if needed.

## How do I rebuild the documentation site?

```bash
./install.sh docs         # install deps + serve at 127.0.0.1:${DOCS_PORT} (default 8000)
./install.sh docs-build   # strict build into ./site
```

Manual: `mkdocs serve` (local preview) / `mkdocs build --strict` (site/). Use
`DOCS_PORT` (or `./install.sh`) to change the preview port.