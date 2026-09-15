# Database & Migrations

## Engine

SQLAlchemy 2.x with session-per-request dependency (`app/database.py`).

- **Production:** PostgreSQL via `psycopg2` — `postgresql+psycopg2://...`
- **Development / tests:** SQLite (auto-configured with `StaticPool`)

## Models

| Model       | Purpose                                                          |
|-------------|------------------------------------------------------------------|
| `User`      | Portal/API users: `username`, `email`, `hashed_password`, `role` (`admin`/`viewer`), `is_active`, `last_login`. |
| `IPAddress` | IP inventory: `ip_address`, `subnet_prefix`, `hostname`, `device_type`, `status`, `allocation_type`, `assigned_date`, `expiry_date`, `description`. |
| `Network`   | Network ranges: `network_name`, `network_range`, `cidr`, `gateway`, `dns`, `description`. |
| `Device`    | Devices: `hostname`, `vendor`, `model`, `serial`, `ip_address`, `status`, `location`, `description`. |
| `IPHistory` | Change log for IP addresses (`ip_id` FK, `address`, `change_type`, `old_value`, `new_value`, `changed_by`, `changed_at`). |

## Creating tables

For local development only, set `AUTO_CREATE_TABLES=true` and tables are created
on startup. **In production always use migrations.**

## Migrations (Alembic)

Apply the latest migration to your database:

```bash
alembic upgrade head
```

Generate a new migration after schema changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Migration files live in `alembic/versions/`. The initial migration
(`0001_initial`) creates all tables, indexes (including a unique index on
`ip_addresses.ip_address`), and the `IPHistory` foreign key.

Rollback one revision (with care):

```bash
alembic downgrade -1
```

## Backups (PostgreSQL)

```bash
pg_dump -U ipam -h localhost ipam > ipam-backup-$(date +%F).sql
```

Restore:

```bash
psql -U ipam -h localhost ipam < ipam-backup-YYYY-MM-DD.sql
```