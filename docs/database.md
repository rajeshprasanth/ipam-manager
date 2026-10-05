# Database & Migrations

## Engine

SQLAlchemy 2.x with session-per-request dependency (`app/database.py`).

- **Production:** PostgreSQL via `psycopg2` — `postgresql+psycopg2://...`
- **Development / tests:** SQLite (auto-configured with `StaticPool`)

## Models

| Model       | Purpose                                                          |
|-------------|------------------------------------------------------------------|
| `User`      | Portal/API users: `username`, `email`, `hashed_password`, `role` (`admin`/`viewer`), `is_active`, `last_login`. |
| `IPAddress` | IP inventory: `ip_address`, `subnet_prefix`, `hostname`, `device_type`, `status`, `allocation_type`, `assigned_date`, `expiry_date`, `description`, `mac_addresses` (JSON list, max 20), `device_id` (FK → `devices.id`, `ON DELETE SET NULL`). |
| `Network`   | Network ranges: `network_name`, `network_range`, `cidr`, `gateway`, `dns`, `description`. |
| `Device`    | Configuration items: `hostname`, `vendor`, `device_model`, `serial_number`, `status`, `location`, `description`, plus the full CMDB attribute set (see below). |
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

`0002_ip_address_mac_addresses` replaces `ip_addresses.mac_address` (a single
`varchar(17)`) with `ip_addresses.mac_addresses` (a JSON list). Existing values
are wrapped into a one element array, so no MAC data is lost. The downgrade is
lossy in the other direction: it keeps only the first MAC of each list.

`0003_ip_address_device_id` adds `ip_addresses.device_id`, an indexed foreign key
to `devices.id` with `ON DELETE SET NULL`. One device may hold many IP addresses
(multi-homed hosts); deleting a device leaves its addresses in place, simply
unassigned. SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set,
which `app/database.py` enables so SQLite and PostgreSQL behave identically.

Rollback one revision (with care):

```bash
alembic downgrade -1
```

`0004_device_cmdb_fields` adds 85 enterprise CMDB attributes to `devices` plus an
indexed self-referencing `parent_device_id` (`ON DELETE SET NULL`) for
hypervisor/enclosure containment. Every column is nullable except the ones
backing a default (`device_class`, `lifecycle_status`, `criticality`,
`discovery_source`, `is_virtual`, `authorized_use`, `monitoring_enabled`), so
existing rows upgrade without a backfill. `asset_tag` gets a **unique** index —
it is the key finance and audit reconcile on. Nulls are still allowed to repeat,
so devices without an asset tag can coexist.

## Device CMDB attributes

Grouped as they appear in the device form. Controlled vocabularies are defined
once in `app/models.py` and reused by the `Literal` types in `app/schemas.py`.

| Group | Attributes |
|-------|------------|
| Identification | `asset_tag` (unique), `inventory_id`, `instance_id`, `barcode`, `device_uuid` |
| Classification | `device_class`, `device_subtype`, `manufacturer`, `part_number`, `chassis_type`, `is_virtual`, `parent_device_id` |
| Lifecycle | `lifecycle_status`, `purchase_date`, `warranty_start`, `warranty_end`, `install_date`, `decommission_date`, `last_audit_date`, `next_review_date` |
| Financial | `purchase_cost`, `currency`, `po_number`, `contract_number`, `supplier`, `lease_end` |
| Organisation | `cost_center`, `business_unit`, `asset_custodian`, `managed_by`, `approver` |
| Location & placement | `site_code`, `address`, `city`, `state_province`, `postal_code`, `country`, `floor`, `rack_position`, `rack_units`, `slot_position`, `latitude`, `longitude`, `timezone` |
| Technical | `bios_version`, `os_version`, `cpu_model`, `cpu_count`, `memory_gb`, `storage_gb`, `power_draw_w`, `weight_kg`, `mac_addresses` (JSON list, max 20) |
| Network | `primary_ip`, `management_ip`, `network_segment`, `dns_domain`, `port_count`, `uplink_speed_mbps` |
| Service & resilience | `service_name`, `service_group`, `application`, `redundancy_group`, `cluster_name`, `rto_minutes`, `rpo_minutes`, `maintenance_window`, `support_ticket`, `change_reference` |
| Security & compliance | `criticality`, `data_classification`, `compliance_status`, `compliance_framework`, `authorized_use`, `patch_status`, `patch_due_date`, `antivirus_status`, `monitoring_enabled`, `monitoring_agent`, `last_seen`, `backup_status`, `last_backup_date`, `discovery_source`, `last_cmdb_sync` |

Indexed for reporting: `asset_tag`, `inventory_id`, `device_class`,
`lifecycle_status`, `cost_center`, `site_code`, `criticality`,
`parent_device_id`.

`0005_network_ipam_fields` adds the IPAM attributes to `networks` and links
addresses to their subnet. Concretely:

- `networks` gains `address_family`, `gateway`, `dns_servers` (JSON list),
  `domain_name`, `vrf`, the DHCP scope, the VLAN span, ownership/governance
  fields, `status`, `tags`, `notes`, and an indexed self-referencing
  `parent_network_id` (`ON DELETE SET NULL`) for supernet aggregation.
- `ip_addresses` gains `subnet_id` (indexed FK to `networks.id`,
  `ON DELETE SET NULL`), `is_primary`, and the allocation-governance columns
  `allocation_method`, `reverse_dns`, `redundancy_group`, `shared_with`,
  `status_reason`, `status_changed_at`, `approved_by`, `discovery_source`.

`address_family` is derived from `cidr` on every write, so it cannot disagree
with the block it describes.

The upgrade **backfills `subnet_id`**: each address is linked to the most
specific subnet whose CIDR contains it. Addresses outside every known subnet,
and networks whose `cidr` will not parse, are skipped and left null. The
downgrade drops the new columns, so the backfilled links are lost.

`ip_addresses.subnet_id` uses `ON DELETE SET NULL` rather than `CASCADE`:
deleting a subnet must not silently delete the addresses inside it. Same for
`networks.parent_network_id` — removing a supernet orphans its children instead
of removing them.

## Network attributes

| Group | Attributes |
|-------|------------|
| Addressing | `cidr`, `address_family`, `gateway`, `dns_servers` (JSON list, max 10), `domain_name`, `vrf`, `subnet_mask`, `broadcast_address` |
| DHCP | `dhcp_enabled`, `dhcp_server`, `dhcp_range_start`, `dhcp_range_end` |
| VLAN span | `vlan_id`, `vlan_name`, `vlan_range_start`, `vlan_range_end` |
| Ownership | `environment`, `tenant`, `criticality`, `owner`, `contact_email`, `cost_center`, `site_code`, `datacenter` |
| Lifecycle | `status`, `tags`, `notes`, `parent_network_id` (supernet) |

Indexed for reporting: `address_family`, `environment`, `criticality`,
`status`, `parent_network_id`.

Enforced on write:

- the CIDR must parse, and `address_family` follows from it;
- `gateway` and `broadcast_address` must fall inside the CIDR;
- `dhcp_range_*` and `vlan_range_*` must be given as a pair, must not be
  inverted, must not mix IPv4 with IPv6, and must fall inside the CIDR;
- unusable `dns_servers` entries are dropped and duplicates collapsed;
- **overlapping CIDRs are rejected**, so a subnet has exactly one owner. The
  supernet/subnet pairs implied by `parent_network_id` are the exception;
- a parent network must exist, must contain the child CIDR, must not be the
  network itself, and must not create a cycle.

## IP Address attributes

Added on top of the original inventory columns:

| Group | Attributes |
|-------|------------|
| Subnet | `subnet_id` (FK to `networks.id`), `is_primary` |
| Allocation | `allocation_method`, `discovery_source` |
| Naming | `reverse_dns`, `redundancy_group`, `shared_with` |
| Governance | `status_reason`, `status_changed_at`, `approved_by` |

Enforced on write:

- `subnet_id` must exist, and the address must fall inside that subnet and match
  its address family;
- when `subnet_id` is omitted, the most specific containing subnet is detected
  automatically; if nothing matches, the link is left null;
- a device may have at most **one** primary address. Marking a second one is
  rejected; clearing the first frees the slot.

## Backups (PostgreSQL)

```bash
pg_dump -U ipam -h localhost ipam > ipam-backup-$(date +%F).sql
```

Restore:

```bash
psql -U ipam -h localhost ipam < ipam-backup-YYYY-MM-DD.sql
```