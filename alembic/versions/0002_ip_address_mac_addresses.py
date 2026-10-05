"""Store multiple MAC addresses per IP address

Revision ID: 0002_ip_address_mac_addresses
Revises: 0001_initial
Create Date: 2026-01-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_ip_address_mac_addresses"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "ip_addresses"


def _wrap_expression(dialect: str) -> str:
    """SQL that turns a single MAC column into a one element JSON array."""
    if dialect == "postgresql":
        return "to_json(ARRAY[mac_address])"
    return "json_array(mac_address)"


def _unwrap_expression(dialect: str) -> str:
    """SQL that reads the first element back out of the JSON array."""
    if dialect == "postgresql":
        return "mac_addresses->>0"
    return "json_extract(mac_addresses, '$[0]')"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("mac_addresses", sa.JSON(), nullable=True))

    expression = _wrap_expression(op.get_bind().dialect.name)
    op.execute(sa.text(
        f"UPDATE {TABLE} SET mac_addresses = {expression} "
        "WHERE mac_address IS NOT NULL AND TRIM(mac_address) <> ''"
    ))

    op.drop_column(TABLE, "mac_address")


def downgrade() -> None:
    op.add_column(TABLE, sa.Column("mac_address", sa.String(length=17), nullable=True))

    expression = _unwrap_expression(op.get_bind().dialect.name)
    op.execute(sa.text(
        f"UPDATE {TABLE} SET mac_address = {expression} "
        "WHERE mac_addresses IS NOT NULL AND json_array_length(mac_addresses) > 0"
    ))

    op.drop_column(TABLE, "mac_addresses")
