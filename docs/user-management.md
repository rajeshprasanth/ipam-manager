# User Management

User management is **admin-only** and available at `/users`.

Admins can:

- Create users with a chosen role (`admin` or `viewer`).
- Edit user details (full name, email, role, active status).
- Toggle a user **enabled/disabled** — disabled users cannot authenticate.
- Reset a user's password from the UI.
- Delete users (except themselves and the last active admin).

## Creating a user (web)

1. Sign in as an admin.
2. Go to **Users** → **Add User**.
3. Choose the role: **Admin** (full control) or **Viewer** (read-only).
4. Set an initial password and save.

## Creating a user (API)

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"username":"ops1","email":"ops1@example.com","password":"a-strong-password","role":"viewer","full_name":"Ops One"}'
```

## The first administrator

There is **no default account**. The very first admin must be created from the
command line on the server:

```bash
python -m app.scripts.create_admin \
    --username admin \
    --email admin@example.com \
    --password "a-strong-password"
```

This script also handles the **password-recovery** case: see
[Troubleshooting → I forgot the admin password](troubleshooting.md#i-forgot-the-admin-password-how-do-i-recover).