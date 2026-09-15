# Troubleshooting & FAQ

## What are the default username and password?

**There are none.** The application has no default account. The first
administrator must be created after installation:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

## I forgot the admin password — how do I recover?

Run the create-admin script again **with the same username**. It updates the
existing account instead of failing:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-new-strong-password"
```

This resets the password, restores the `admin` role, and re-activates the
account. Sign in with the new password immediately.

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
mkdocs build     # site/ directory
mkdocs serve     # local preview
```