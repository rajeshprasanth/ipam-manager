# REST API

Base URL: `http://localhost:8076/api` — interactive docs at `/docs` (OpenAPI).

All endpoints (except login) require:

```
Authorization: Bearer <access_token>
```

Roles: **A** = admin only, **V** = admin or viewer (read-only).

## Auth

### `POST /api/auth/login` — obtain a JWT

```json
{ "username": "admin", "password": "your-password" }
```

### `GET /api/auth/me` — current user (any authenticated role)

## Users

| Method | Path             | Role | Description |
|--------|------------------|------|-------------|
| GET    | `/api/users`     | A    | List users  |
| GET    | `/api/users/{id}`| A    | Get user    |
| POST   | `/api/users`     | A    | Create user |
| PATCH  | `/api/users/{id}`| A    | Update user (role, active, full_name, email) |
| DELETE | `/api/users/{id}`| A    | Delete user |
| POST   | `/api/users/{id}/reset-password` | A | Reset password |

Guards: you cannot modify your own role/active status, and the last active admin
is protected.

## IP Addresses

| Method | Path                 | Role | Description |
|--------|----------------------|------|-------------|
| GET    | `/api/ip-addresses`  | V    | List with `page`/`per_page`/`q` (returns `items`, `total`, `page`) |
| GET    | `/api/ip-addresses/{id}` | V | Get one |
| POST   | `/api/ip-addresses`  | A    | Create |
| PATCH  | `/api/ip-addresses/{id}` | A | Update |
| DELETE | `/api/ip-addresses/{id}` | A | Delete |
| GET    | `/api/ip-addresses/{id}/history` | V | Change history |

IP validation is enforced (valid IPv4/IPv6, `subnet_prefix` 0–32 for IPv4); a
duplicate IP returns `409`.

## Networks

| Method | Path                 | Role | Description |
|--------|----------------------|------|-------------|
| GET    | `/api/networks`      | V    | List |
| GET    | `/api/networks/{id}` | V    | Get one |
| POST   | `/api/networks`      | A    | Create |
| PATCH  | `/api/networks/{id}` | A    | Update |
| DELETE | `/api/networks/{id}` | A    | Delete |

## Devices

| Method | Path                 | Role | Description |
|--------|----------------------|------|-------------|
| GET    | `/api/devices`       | V    | List |
| GET    | `/api/devices/{id}`  | V    | Get one |
| POST   | `/api/devices`       | A    | Create |
| PATCH  | `/api/devices/{id}`  | A    | Update |
| DELETE | `/api/devices/{id}`  | A    | Delete |

## Stats

### `GET /api/stats`

Top-level counts plus per-status IP breakdown:

```json
{
  "networks": 4,
  "devices": 12,
  "ip_addresses": 320,
  "ip_stats": {
    "total": 320,
    "available": 105,
    "active": 180,
    "reserved": 20,
    "deprecated": 15
  }
}
```

## Error responses

| Code | Meaning |
|------|---------|
| 401   | Missing/invalid token or bad login |
| 403   | Authenticated but insufficient role / disabled account |
| 404   | Resource not found |
| 409   | Duplicate (e.g. IP already exists) |
| 422   | Validation error |
| 204   | Successful delete |