"""Add network addressing attributes and link IP addresses to subnets

Revision ID: 0005_network_ipam_fields
Revises: 0004_device_cmdb_fields
Create Date: 2026-01-05 00:00:00

Two gaps are closed here:

* ``networks`` gains the attributes an IPAM needs to describe a subnet --
  gateway, DNS, VRF, environment, VLAN span, DHCP scope, ownership and
  lifecycle -- plus a self-referencing ``parent_network_id`` for aggregation
  (supernet/child subnet).
* ``ip_addresses.subnet_id`` links an address to its declared subnet. Previously
  ``network_segment`` was free text, so the address and network inventories
  could not be joined. The upgrade backfills ``subnet_id`` for rows whose IP
  falls inside a known subnet.

``ip_addresses.is_primary`` marks the management address on a multi-homed host,
and the assignment-governance columns record how and under whose authority an
address was allocated.

All columns are nullable except the ones backing a default, so existing rows
upgrade without a backfill.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_network_ipam_fields"
down_revision: Union[str, None] = "0004_device_cmdb_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NETWORKS = "networks"
IP_ADDRESSES = "ip_addresses"
PARENT_NETWORK_CONSTRAINT = "fk_networks_parent_network_id_networks"
SUBNET_CONSTRAINT = "fk_ip_addresses_subnet_id_networks"


def _s(length: int) -> sa.String:
    return sa.String(length)


def _server_default(value: str | None):
    """Server defaults that SQLite batch mode is able to clone.

    Alembic copies columns through ``_copy()`` in batch mode, which chokes on a
    raw ``sa.text()``; plain strings become quoted literals and ``sa.false()``
    keeps booleans real booleans in PostgreSQL.
    """
    if value is None:
        return None
    if value == "false":
        return sa.false()
    if value == "true":
        return sa.true()
    return value


NETWORK_COLUMNS: list[tuple[str, sa.types.TypeEngine, bool, str | None]] = [
    # addressing
    ("address_family", _s(5), False, "IPv4"),
    ("gateway", _s(39), True, None),
    ("dns_servers", sa.JSON(), True, None),
    ("domain_name", _s(255), True, None),
    ("vrf", _s(100), True, None),
    ("dhcp_enabled", sa.Boolean(), False, "false"),
    ("dhcp_server", _s(100), True, None),
    ("dhcp_range_start", _s(39), True, None),
    ("dhcp_range_end", _s(39), True, None),
    # vlan span
    ("vlan_name", _s(100), True, None),
    ("vlan_range_start", _s(39), True, None),
    ("vlan_range_end", _s(39), True, None),
    # ownership & governance
    ("environment", _s(30), True, None),
    ("tenant", _s(100), True, None),
    ("criticality", _s(20), False, "Medium"),
    ("owner", _s(100), True, None),
    ("contact_email", _s(255), True, None),
    ("cost_center", _s(50), True, None),
    ("site_code", _s(50), True, None),
    ("datacenter", _s(100), True, None),
    # lifecycle
    ("status", _s(20), False, "Active"),
    ("tags", _s(255), True, None),
    ("notes", sa.Text(), True, None),
]

IP_COLUMNS: list[tuple[str, sa.types.TypeEngine, bool, str | None]] = [
    # assignment governance
    ("allocation_method", _s(30), False, "Manual"),
    ("reverse_dns", _s(255), True, None),
    ("redundancy_group", _s(100), True, None),
    ("shared_with", sa.Text(), True, None),
    ("status_reason", _s(255), True, None),
    ("status_changed_at", sa.DateTime(timezone=True), True, None),
    ("approved_by", _s(100), True, None),
    ("discovery_source", _s(30), False, "Manual"),
]

NETWORK_INDEXES = [
    ("ix_networks_address_family", ["address_family"], False),
    ("ix_networks_environment", ["environment"], False),
    ("ix_networks_criticality", ["criticality"], False),
    ("ix_networks_status", ["status"], False),
]


def upgrade() -> None:
    with op.batch_alter_table(NETWORKS) as batch:
        for name, type_, nullable, default in NETWORK_COLUMNS:
            batch.add_column(sa.Column(
                name, type_, nullable=nullable, server_default=_server_default(default),
            ))
        batch.add_column(sa.Column("parent_network_id", sa.Integer(), nullable=True))
        batch.create_index("ix_networks_parent_network_id", ["parent_network_id"])
        batch.create_foreign_key(
            PARENT_NETWORK_CONSTRAINT, NETWORKS, ["parent_network_id"], ["id"], ondelete="SET NULL",
        )

    with op.batch_alter_table(IP_ADDRESSES) as batch:
        for name, type_, nullable, default in IP_COLUMNS:
            batch.add_column(sa.Column(
                name, type_, nullable=nullable, server_default=_server_default(default),
            ))
        batch.add_column(sa.Column("subnet_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("is_primary", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
        batch.create_index("ix_ip_addresses_subnet_id", ["subnet_id"])
        batch.create_foreign_key(
            SUBNET_CONSTRAINT, NETWORKS, ["subnet_id"], ["id"], ondelete="SET NULL",
        )

    for name, columns, unique in NETWORK_INDEXES:
        op.create_index(name, NETWORKS, columns, unique=unique)

    _backfill_subnets()


def _backfill_subnets() -> None:
    """Point existing addresses at a declared subnet when one contains them.

    Implemented in Python rather than SQL because containment has to be tested
    against parsed CIDR blocks, which is not portable across backends. A network
    row without a parseable ``cidr`` is simply skipped.
    """
    bind = op.get_bind()
    networks = bind.execute(sa.text(
        "SELECT id, cidr FROM networks WHERE cidr IS NOT NULL"
    )).fetchall()
    if not networks:
        return

    import ipaddress

    blocks = []
    for network_id, cidr in networks:
        try:
            blocks.append((network_id, ipaddress.ip_network(str(cidr), strict=False)))
        except ValueError:
            continue
    if not blocks:
        return

    rows = bind.execute(sa.text(
        "SELECT id, ip_address FROM ip_addresses WHERE subnet_id IS NULL"
    )).fetchall()
    updates = []
    for address_id, address in rows:
        try:
            parsed = ipaddress.ip_address(str(address))
        except ValueError:
            continue
        # Longest prefix wins, so an address inside two nested subnets links to
        # the most specific one.
        best = None
        for network_id, block in blocks:
            if parsed.version != block.version or parsed not in block:
                continue
            if best is None or block.prefixlen > best[1].prefixlen:
                best = (network_id, block)
        if best is not None:
            updates.append({"id": address_id, "subnet_id": best[0]})

    if updates:
        bind.execute(
            sa.text("UPDATE ip_addresses SET subnet_id = :subnet_id WHERE id = :id"),
            updates,
        )


def downgrade() -> None:
    for name, _columns, _unique in reversed(NETWORK_INDEXES):
        op.drop_index(name, table_name=NETWORKS)

    with op.batch_alter_table(IP_ADDRESSES) as batch:
        batch.drop_constraint(SUBNET_CONSTRAINT, type_="foreignkey")
        batch.drop_index("ix_ip_addresses_subnet_id")
        batch.drop_column("subnet_id")
        batch.drop_column("is_primary")
        for name, _type, _nullable, _default in reversed(IP_COLUMNS):
            batch.drop_column(name)

    with op.batch_alter_table(NETWORKS) as batch:
        batch.drop_constraint(PARENT_NETWORK_CONSTRAINT, type_="foreignkey")
        batch.drop_index("ix_networks_parent_network_id")
        batch.drop_column("parent_network_id")
        for name, _type, _nullable, _default in reversed(NETWORK_COLUMNS):
            batch.drop_column(name)