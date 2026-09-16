# Security & Role-Based Access Control

## Roles

Two roles are enforced everywhere — web UI and REST API:

| Role     | Web portal                                   | REST API                       |
|----------|----------------------------------------------|--------------------------------|
| `admin`  | Full CRUD + user management                  | Full CRUD + user management    |
| `viewer` | Read-only pages; no add/edit/delete buttons  | Read endpoints only (403 on writes) |

## Authentication

- Passwords are stored as **bcrypt** hashes (`app/security.py`).
- On login the server issues a **JWT** (`HS256`), stored in an **HTTP-only
  cookie** named `access_token`.
- Cookies carry `SameSite=Lax` (or `Strict`), and `Secure` when
  `COOKIE_SECURE=true`.
- The `User`-attaching middleware runs on every request and populates
  `request.state.user`.

### Guards

| Dependency                 | Where used          | Behavior                                   |
|----------------------------|---------------------|---------------------------------------------|
| `get_current_user_web`     | Web routes          | Redirects to `/login` if unauthenticated.   |
| `require_admin_web`        | Web admin routes    | Redirects to `/dashboard` for non-admins.   |
| `get_current_user_api`     | API routes          | Returns `401` if token missing/invalid.     |
| `require_admin_api`        | API admin routes    | Returns `403` for non-admins.               |

### API authentication

Log in to obtain a JWT:

```bash
curl -s -X POST http://localhost:8076/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

Response:

```json
{ "access_token": "<jwt>", "token_type": "bearer", "user": { "id": 1, "username": "admin", "role": "admin" } }
```

Use the token on subsequent requests:

```bash
curl -H "Authorization: Bearer <jwt>" http://localhost:8076/api/ip-addresses
```

## CSRF protection (web forms)

- A random CSRF token is issued as the `ipam_csrf` cookie.
- Every POST form must include a matching `_csrf` hidden field.
- The `verify_csrf` dependency rejects missing/mismatched tokens with `400`.

## Flash messages

Session status messages are signed (so they cannot be forged), transported in
the `ipam_flash` cookie, and cleared after they are rendered.

## OAuth / social sign-in (Google, GitHub)

The portal supports signing in with **Google** or **GitHub** in addition to local
username/password accounts.

- Providers appear on the login page **only when** the matching
  `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (or `GITHUB_*`) pair is configured.
- Both follow the standard **authorization-code flow**: the server redirects to
  the provider, exchanges the code for a token server-side, and fetches the
  user's **verified** email. Provider secrets never reach the browser.
- The **state parameter** guards the callback against CSRF (a signed, HTTP-only
  `oauth_state_<provider>` cookie is checked and then discarded).

### Account matching & provisioning

- Accounts are matched to portal users by **verified email** (case-insensitive).
- If no local user matches, one is **automatically created** with the
  read-only `viewer` role (`full_name` from the provider). Promote it to admin
  from **Users** in the portal; the first administrator still has to be
  bootstrapped with `create_admin`.
- OAuth-provisioned accounts have **no local password** — local credentials
  cannot authenticate them. Grant one by resetting the password from **Users**.

### Callback URLs

- Google: `<public_base_url>/auth/callback/google`
- GitHub: `<public_base_url>/auth/callback/github`

`public_base_url` is `OAUTH_BASE_URL` if set, otherwise derived from the request
`Host` header. Behind a proxy, set `OAUTH_BASE_URL` explicitly.

## Self-lockout guards

You cannot lock yourself out of the last admin:

- You cannot demote, disable, or delete **your own** account.
- You cannot demote/disable the **last active admin**.
- A user who is `is_active=false` cannot authenticate.

## Recommended production hardening

1. Set a strong, unique `SECRET_KEY`.
2. Set `COOKIE_SECURE=true` and serve over HTTPS (terminate TLS at a proxy).
3. Set `AUTO_CREATE_TABLES=false` and use Alembic migrations.
4. Keep `DEBUG=false`.
5. Rotate the admin password periodically; keep `last_login` visible for audit.