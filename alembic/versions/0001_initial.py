"""Initial schema for IPAM Manager

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "ip_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address", sa.String(length=39), nullable=False),
        sa.Column("subnet_prefix", sa.Integer(), nullable=False),
        sa.Column("gateway", sa.String(length=39), nullable=True),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("network_segment", sa.String(length=100), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=True),
        sa.Column("interface_name", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Available"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assigned_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("responsible_person", sa.String(length=100), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column("allocation_type", sa.String(length=20), nullable=False, server_default="Static"),
        sa.Column("fqdn", sa.String(length=255), nullable=True),
        sa.Column("device_model", sa.String(length=100), nullable=True),
        sa.Column("vendor", sa.String(length=100), nullable=True),
        sa.Column("operating_system", sa.String(length=100), nullable=True),
        sa.Column("firmware", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ping_status", sa.String(length=20), nullable=True),
        sa.Column("availability", sa.String(length=20), nullable=True),
        sa.Column("related_tickets", sa.Text(), nullable=True),
        sa.Column("incidents", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("dns_records", sa.Text(), nullable=True),
        sa.Column("security_group", sa.String(length=100), nullable=True),
        sa.Column("acl_applied", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ip_address"),
    )
    op.create_index("ix_ip_addresses_ip_address", "ip_addresses", ["ip_address"], unique=True)
    op.create_index("ix_ip_addresses_status", "ip_addresses", ["status"])
    op.create_index("ix_ip_addresses_device_type", "ip_addresses", ["device_type"])
    op.create_index("ix_ip_addresses_vlan_id", "ip_addresses", ["vlan_id"])

    op.create_table(
        "networks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("network_name", sa.String(length=100), nullable=False),
        sa.Column("network_range", sa.String(length=50), nullable=False),
        sa.Column("cidr", sa.String(length=50), nullable=False),
        sa.Column("subnet_mask", sa.String(length=15), nullable=True),
        sa.Column("broadcast_address", sa.String(length=39), nullable=True),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("network_role", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_networks_vlan_id", "networks", ["vlan_id"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("fqdn", sa.String(length=255), nullable=True),
        sa.Column("device_model", sa.String(length=100), nullable=True),
        sa.Column("vendor", sa.String(length=100), nullable=True),
        sa.Column("operating_system", sa.String(length=100), nullable=True),
        sa.Column("firmware", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("rack", sa.String(length=50), nullable=True),
        sa.Column("room", sa.String(length=50), nullable=True),
        sa.Column("datacenter", sa.String(length=100), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("responsible_person", sa.String(length=100), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("team", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_devices_hostname", "devices", ["hostname"])

    op.create_table(
        "ip_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address", sa.String(length=39), nullable=False),
        sa.Column("ip_id", sa.Integer(), nullable=True),
        sa.Column("previous_hostname", sa.String(length=255), nullable=True),
        sa.Column("previous_assigned_to", sa.String(length=255), nullable=True),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("change_reason", sa.String(length=255), nullable=True),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.Column("change_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ip_id"], ["ip_addresses.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ip_history_ip_address", "ip_history", ["ip_address"])


def downgrade() -> None:
    op.drop_table("ip_history")
    op.drop_table("devices")
    op.drop_table("networks")
    op.drop_table("ip_addresses")
    op.drop_table("users")