"""Add enterprise CMDB fields to devices

Revision ID: 0004_device_cmdb_fields
Revises: 0003_ip_address_device_id
Create Date: 2026-01-04 00:00:00

Adds the configuration-item attributes an enterprise CMDB expects -- asset
identity, classification, lifecycle, financial, organisational, placement,
technical, service, and compliance attributes -- so devices can be reconciled
against finance, audit and discovery tooling instead of only tracking IPs.

Every column is nullable except the handful that back an existing default
(``device_class``, ``lifecycle_status``, ``criticality``, ``discovery_source``
and the two booleans), so existing rows upgrade without a backfill.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_device_cmdb_fields"
down_revision: Union[str, None] = "0003_ip_address_device_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "devices"
PARENT_CONSTRAINT = "fk_devices_parent_device_id_devices"


def _s(length: int) -> sa.String:
    return sa.String(length)


def _server_default(value: str | None):
    """Build a server default batch mode is able to copy.

    Alembic's SQLite batch ``add_column`` clones columns via ``_copy()``, which
    only understands ``DefaultClause`` wrappers -- a raw ``sa.text()`` raises
    ``AttributeError: 'TextClause' object has no attribute '_copy'``. Plain
    strings are emitted as quoted literals, and booleans go through
    ``sa.false()``/``sa.true()`` so Postgres sees a real boolean rather than the
    string ``'false'``.
    """
    if value is None:
        return None
    if value == "false":
        return sa.false()
    if value == "true":
        return sa.true()
    return value


# (column name, column type, nullable, server_default) -- kept in one table so
# the model and the migration can be diffed by eye.
COLUMNS: list[tuple[str, sa.types.TypeEngine, bool, str | None]] = [
    # identification
    ("asset_tag", _s(64), True, None),
    ("inventory_id", _s(64), True, None),
    ("instance_id", _s(100), True, None),
    ("barcode", _s(64), True, None),
    ("device_uuid", _s(64), True, None),
    # classification
    ("device_class", _s(50), False, "Other"),
    ("device_subtype", _s(100), True, None),
    ("manufacturer", _s(100), True, None),
    ("part_number", _s(100), True, None),
    ("chassis_type", _s(50), True, None),
    ("is_virtual", sa.Boolean(), False, "false"),
    # lifecycle
    ("lifecycle_status", _s(30), False, "In Service"),
    ("purchase_date", sa.Date(), True, None),
    ("warranty_start", sa.Date(), True, None),
    ("warranty_end", sa.Date(), True, None),
    ("install_date", sa.Date(), True, None),
    ("decommission_date", sa.Date(), True, None),
    ("last_audit_date", sa.Date(), True, None),
    ("next_review_date", sa.Date(), True, None),
    # financial
    ("purchase_cost", sa.Numeric(12, 2), True, None),
    ("currency", _s(3), True, None),
    ("po_number", _s(50), True, None),
    ("contract_number", _s(50), True, None),
    ("supplier", _s(100), True, None),
    ("lease_end", sa.Date(), True, None),
    # organisation
    ("cost_center", _s(50), True, None),
    ("business_unit", _s(100), True, None),
    ("asset_custodian", _s(100), True, None),
    ("managed_by", _s(100), True, None),
    ("approver", _s(100), True, None),
    # location / placement
    ("site_code", _s(50), True, None),
    ("address", sa.Text(), True, None),
    ("city", _s(100), True, None),
    ("state_province", _s(100), True, None),
    ("postal_code", _s(20), True, None),
    ("country", _s(100), True, None),
    ("floor", _s(20), True, None),
    ("rack_position", sa.Integer(), True, None),
    ("rack_units", sa.Integer(), True, None),
    ("slot_position", _s(50), True, None),
    ("latitude", sa.Numeric(10, 7), True, None),
    ("longitude", sa.Numeric(10, 7), True, None),
    ("timezone", _s(50), True, None),
    # technical specification
    ("bios_version", _s(100), True, None),
    ("os_version", _s(100), True, None),
    ("cpu_model", _s(100), True, None),
    ("cpu_count", sa.Integer(), True, None),
    ("memory_gb", sa.Integer(), True, None),
    ("storage_gb", sa.Integer(), True, None),
    ("power_draw_w", sa.Integer(), True, None),
    ("weight_kg", sa.Numeric(8, 2), True, None),
    ("mac_addresses", sa.JSON(), True, None),
    # network identity
    ("primary_ip", _s(39), True, None),
    ("management_ip", _s(39), True, None),
    ("network_segment", _s(100), True, None),
    ("dns_domain", _s(255), True, None),
    ("port_count", sa.Integer(), True, None),
    ("uplink_speed_mbps", sa.Integer(), True, None),
    # service & resilience
    ("service_name", _s(100), True, None),
    ("service_group", _s(100), True, None),
    ("application", _s(100), True, None),
    ("redundancy_group", _s(100), True, None),
    ("cluster_name", _s(100), True, None),
    ("rto_minutes", sa.Integer(), True, None),
    ("rpo_minutes", sa.Integer(), True, None),
    ("maintenance_window", _s(100), True, None),
    ("support_ticket", _s(50), True, None),
    ("change_reference", _s(50), True, None),
    # security & compliance
    ("criticality", _s(20), False, "Medium"),
    ("data_classification", _s(30), True, None),
    ("compliance_status", _s(30), True, None),
    ("compliance_framework", _s(100), True, None),
    ("authorized_use", sa.Boolean(), False, "true"),
    ("patch_status", _s(30), True, None),
    ("patch_due_date", sa.Date(), True, None),
    ("antivirus_status", _s(30), True, None),
    ("monitoring_enabled", sa.Boolean(), False, "false"),
    ("monitoring_agent", _s(100), True, None),
    ("last_seen", sa.DateTime(timezone=True), True, None),
    ("backup_status", _s(30), True, None),
    ("last_backup_date", sa.DateTime(timezone=True), True, None),
    ("discovery_source", _s(30), False, "Manual"),
    ("last_cmdb_sync", sa.DateTime(timezone=True), True, None),
]

INDEXES: list[tuple[str, list[str], bool]] = [
    ("ix_devices_asset_tag", ["asset_tag"], True),
    ("ix_devices_inventory_id", ["inventory_id"], False),
    ("ix_devices_device_class", ["device_class"], False),
    ("ix_devices_lifecycle_status", ["lifecycle_status"], False),
    ("ix_devices_cost_center", ["cost_center"], False),
    ("ix_devices_site_code", ["site_code"], False),
    ("ix_devices_criticality", ["criticality"], False),
]


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        for name, type_, nullable, default in COLUMNS:
            batch.add_column(sa.Column(
                name, type_, nullable=nullable, server_default=_server_default(default),
            ))
        batch.add_column(sa.Column("parent_device_id", sa.Integer(), nullable=True))
        batch.create_index("ix_devices_parent_device_id", ["parent_device_id"])
        batch.create_foreign_key(
            PARENT_CONSTRAINT, TABLE, ["parent_device_id"], ["id"], ondelete="SET NULL",
        )

    for name, columns, unique in INDEXES:
        op.create_index(name, TABLE, columns, unique=unique)


def downgrade() -> None:
    for name, _columns, _unique in reversed(INDEXES):
        op.drop_index(name, table_name=TABLE)

    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(PARENT_CONSTRAINT, type_="foreignkey")
        batch.drop_index("ix_devices_parent_device_id")
        batch.drop_column("parent_device_id")
        for name, _type, _nullable, _default in reversed(COLUMNS):
            batch.drop_column(name)