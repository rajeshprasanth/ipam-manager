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

MAC addresses are submitted as `mac_addresses`, a list of up to 20 entries
(format `XX:XX:XX:XX:XX:XX`, `:` or `-` separators). A single separated string is
also accepted and blanks/duplicates are dropped:

```json
{
  "ip_address": "192.168.1.10",
  "subnet_prefix": 24,
  "mac_addresses": ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]
}
```

### Assigning addresses to devices

Set `device_id` to link an address to a registered device; omit it (or send
`null`) to leave the address unassigned. One device may hold several addresses,
so a multi-homed host uses one entry per interface. An unknown `device_id`
returns `404`, and deleting a device leaves its addresses in place but
unassigned.

```json
{
  "ip_address": "192.168.1.10",
  "subnet_prefix": 24,
  "device_id": 3,
  "interface_name": "eth0"
}
```

`GET /api/ip-addresses` also accepts `device_id` to filter by device. Device
responses include the addresses they hold:

```json
{ "id": 3, "hostname": "web-srv-01", "status": "Active", "ip_addresses": ["192.168.1.10", "192.168.1.11"] }
```

### Subnet and allocation attributes

An address belongs to a subnet through `subnet_id`, which references
`/api/networks`. The address must fall inside that subnet and match its address
family, otherwise the write returns `409`.

```json
{
  "ip_address": "192.168.1.10",
  "subnet_prefix": 24,
  "subnet_id": 7,
  "is_primary": true,
  "allocation_method": "Static Reservation",
  "discovery_source": "Network Scan",
  "reverse_dns": "10.1.168.192.in-addr.arpa",
  "redundancy_group": "FHRP-GRP-1",
  "shared_with": "Cluster node B",
  "status_reason": "Reserved for new cluster",
  "status_changed_at": "2026-02-01T10:00:00",
  "approved_by": "Jane Doe"
}
```

`subnet_id` may be omitted. When it is, the most specific subnet containing the
address is detected and stored; if no subnet contains it, the link stays null
rather than guessing.

`is_primary` marks the management address on a multi-homed device. A device may
hold only one; assigning a second returns `409`, and clearing the first frees
the slot. Because a `PATCH` is partial, the check is evaluated against the
stored row merged with your changes.

`allocation_method` and `discovery_source` are controlled vocabularies
(`Manual`, `Static Reservation`, `DHCP`, `DHCP Reservation`, `IPv6 SLAAC`,
`Cluster VIP` and `Manual`, `Network Scan`, `Agent`, `Import`, `API`,
`Hypervisor`); an unknown value returns `422`.

`GET /api/ip-addresses` accepts `subnet_id` and `is_primary` alongside the
existing filters, and `search` also covers `reverse_dns`, `redundancy_group`
and `approved_by`.

Deleting a subnet leaves its addresses in place with `subnet_id` set to null —
the addresses outlive the subnet record.

## Networks

| Method | Path                 | Role | Description |
|--------|----------------------|------|-------------|
| GET    | `/api/networks`      | V    | List |
| GET    | `/api/networks/{id}` | V    | Get one |
| POST   | `/api/networks`      | A    | Create |
| PATCH  | `/api/networks/{id}` | A    | Update |
| DELETE | `/api/networks/{id}` | A    | Delete |

`GET /api/networks` accepts `q`, `environment` and `status`. `q` searches the
name, range, CIDR, VLAN name, VRF, domain, tenant, owner, site code, datacenter,
gateway and tags.

### Network attributes

```json
{
  "network_name": "Corporate",
  "network_range": "10.20.0.0/16",
  "cidr": "10.20.0.0/16",
  "address_family": "IPv4",
  "gateway": "10.20.0.1",
  "dns_servers": ["10.20.0.2", "10.20.0.3"],
  "domain_name": "corp.example.com",
  "vrf": "MGMT",
  "environment": "Production",
  "criticality": "High",
  "owner": "Network Team",
  "contact_email": "netops@example.com",
  "cost_center": "CC-1042",
  "site_code": "BLR-01",
  "datacenter": "DC-East",
  "vlan_id": 100,
  "vlan_name": "USERS",
  "vlan_range_start": "10.20.0.1",
  "vlan_range_end": "10.20.255.254",
  "dhcp_enabled": true,
  "dhcp_server": "10.20.0.5",
  "dhcp_range_start": "10.20.0.100",
  "dhcp_range_end": "10.20.0.200",
  "status": "Active",
  "tags": "pci",
  "parent_network_id": null
}
```

`address_family` is **derived from `cidr`**, so the two cannot disagree; send
the CIDR and the family follows (IPv4 or IPv6).

Validation splits by cause. Field-shape problems return `422`:

- `cidr` must parse;
- `gateway` and `broadcast_address` must fall inside the CIDR;
- `dhcp_range_start`/`dhcp_range_end` and `vlan_range_start`/`vlan_range_end`
  must each be supplied as a pair, must not be inverted, must not mix IPv4 with
  IPv6, and must fall inside the CIDR;
- `environment`, `criticality`, `status` and `address_family` are controlled
  vocabularies.

`dns_servers` is forgiving by design: unusable entries are dropped and
duplicates collapsed, so one bad resolver does not block the network. A
subnet has at most 10.

Topology problems return `409`:

- **overlapping CIDRs are rejected** — a subnet has exactly one owner. Adjacent
  blocks such as `10.20.0.0/24` and `10.20.1.0/24` do not clash, but
  `10.20.5.0/24` inside an existing `10.20.0.0/16` does;
- the one nesting that is allowed is an explicit `parent_network_id`
  supernet/subnet pair, whose overlap is exempt;
- a parent must exist, must contain the child CIDR, must not be the network
  itself, and must not form a cycle.

```json
{
  "network_name": "Users-VLAN",
  "network_range": "10.20.5.0/24",
  "cidr": "10.20.5.0/24",
  "parent_network_id": 2
}
```

Deleting a supernet sets `parent_network_id` to null on its children rather
than deleting them.

## Devices

| Method | Path                 | Role | Description |
|--------|----------------------|------|-------------|
| GET    | `/api/devices`       | V    | List |
| GET    | `/api/devices/{id}`  | V    | Get one |
| POST   | `/api/devices`       | A    | Create |
| PATCH  | `/api/devices/{id}`  | A    | Update |
| DELETE | `/api/devices/{id}`  | A    | Delete |

### CMDB attributes

`POST` and `PATCH` accept the full configuration-item attribute set grouped
below; `GET` returns all of them alongside the device's assigned
`ip_addresses`. The field groups, vocabularies and constraints are documented
in [database.md](database.md#device-cmdb-attributes).

| Group | Example fields |
|-------|----------------|
| Identification | `asset_tag` (unique), `inventory_id`, `instance_id`, `barcode`, `device_uuid` |
| Classification | `device_class`, `device_subtype`, `manufacturer`, `part_number`, `chassis_type`, `is_virtual`, `parent_device_id` |
| Lifecycle | `lifecycle_status`, `purchase_date`, `warranty_start`, `warranty_end`, `install_date`, `decommission_date`, `last_audit_date`, `next_review_date` |
| Financial | `purchase_cost`, `currency`, `po_number`, `contract_number`, `supplier`, `lease_end` |
| Organisation | `cost_center`, `business_unit`, `asset_custodian`, `managed_by`, `approver` |
| Location | `site_code`, `address`, `city`, `state_province`, `postal_code`, `country`, `floor`, `rack_position`, `rack_units`, `slot_position`, `latitude`, `longitude`, `timezone` |
| Technical | `bios_version`, `os_version`, `cpu_model`, `cpu_count`, `memory_gb`, `storage_gb`, `power_draw_w`, `weight_kg`, `mac_addresses` |
| Network | `primary_ip`, `management_ip`, `network_segment`, `dns_domain`, `port_count`, `uplink_speed_mbps` |
| Service | `service_name`, `service_group`, `application`, `redundancy_group`, `cluster_name`, `rto_minutes`, `rpo_minutes`, `maintenance_window`, `support_ticket`, `change_reference` |
| Security | `criticality`, `data_classification`, `compliance_status`, `compliance_framework`, `authorized_use`, `patch_status`, `patch_due_date`, `antivirus_status`, `monitoring_enabled`, `backup_status`, `discovery_source` |

Controlled vocabularies (`device_class`, `lifecycle_status`, `criticality`,
`data_classification`, `compliance_status`, `patch_status`, `antivirus_status`,
`backup_status`, `discovery_source`) are validated; an unknown value returns
`422`. `currency` is upper-cased, `mac_addresses` is normalised and
de-duplicated, and `primary_ip` / `management_ip` are parsed as IP addresses.

```bash
curl -X POST http://localhost:8076/api/devices \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"hostname":"esx-host-01","asset_tag":"AT-100234","device_class":"Server",
       "lifecycle_status":"In Service","criticality":"Critical",
       "rack_position":12,"memory_gb":128,"purchase_cost":"18999.99","currency":"EUR"}'
```

`409` is returned when a rule cannot be expressed as a type constraint: a
duplicate `asset_tag` (case-insensitive), a `parent_device_id` that does not
exist, a device made its own parent, or a change that would create a circular
`parent_device_id` chain.

## Stats

### `GET /api/stats`

Per-status breakdowns for IP addresses and devices, plus assignment totals:

```json
{
  "ip_stats": {
    "total": 320,
    "available": 105,
    "active": 180,
    "reserved": 20,
    "deprecated": 15
  },
  "device_stats": {
    "total": 12,
    "active": 9,
    "inactive": 2,
    "maintenance": 1
  },
  "network_count": 4,
  "device_count": 12,
  "user_count": 5,
  "assigned_ip_count": 240,
  "unassigned_ip_count": 80
}
```

These are the same figures the dashboard renders, so both stay in sync.

## Error responses

| Code | Meaning |
|------|---------|
| 401   | Missing/invalid token or bad login |
| 403   | Authenticated but insufficient role / disabled account |
| 404   | Resource not found |
| 409   | Duplicate (e.g. IP already exists) |
| 422   | Validation error |
| 204   | Successful delete |