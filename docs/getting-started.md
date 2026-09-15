# Getting Started

## Requirements

- Python **3.10+** (developed and tested on 3.14)
- PostgreSQL 16 for production (optional for local dev)
- A venv or virtualenv

## 1. Clone and install

```bash
git clone https://github.com/rajeshprasanth/ipam-manager.git
cd ipam-manager

python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# optional: dev + docs + test tooling
pip install -r requirements-dev.txt
```

## 2. Configure

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
(`AUTO_CREATE_TABLES=true` creates tables on startup). To use PostgreSQL, set:

```dotenv
DATABASE_URL=postgresql+psycopg2://ipam:ipam@localhost:5432/ipam
```

## 3. Create the first administrator

There is **no default username or password**. Bootstrap the first admin:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

If `--password` is omitted you will be prompted interactively.

??? note "Idempotent & recoverable"
    Re-running the script with the same username **does not fail** — it updates
    the existing account: resets the password, forces the role to `admin`, and
    re-activates it. This is also your password-recovery path (see
    [Troubleshooting](troubleshooting.md)).

## 4. Run it

Development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or:

```bash
python run.py
```

## 5. Verify

| URL            | What to check                                  |
|----------------|------------------------------------------------|
| `http://localhost:8000/`      | Enterprise landing page                  |
| `http://localhost:8000/login` | Sign in with your new admin credentials  |
| `http://localhost:8000/dashboard` | Dashboard with IP / network stats   |
| `http://localhost:8000/docs`  | FastAPI auto-generated OpenAPI docs     |

## 6. Optional: enable social sign-in

Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` (and/or `GITHUB_CLIENT_ID` +
`GITHUB_CLIENT_SECRET`) in `.env`, plus `OAUTH_BASE_URL` if behind a proxy.
"Continue with Google / GitHub" buttons then appear on the login page. See
[Security & RBAC → OAuth](security.md#oauth-social-sign-in-google-github).

## 7. Run the test suite

```bash
pytest
```

The suite uses an in-memory SQLite database and needs no external services.
It seeds `admin` and `viewer` test accounts automatically (see `tests/conftest.py`).