"""Link IP addresses to devices

Revision ID: 0003_ip_address_device_id
Revises: 0002_ip_address_mac_addresses
Create Date: 2026-01-03 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_ip_address_device_id"
down_revision: Union[str, None] = "0002_ip_address_mac_addresses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "ip_addresses"
CONSTRAINT = "fk_ip_addresses_device_id_devices"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("device_id", sa.Integer(), nullable=True))
        batch.create_index("ix_ip_addresses_device_id", ["device_id"])
        batch.create_foreign_key(
            CONSTRAINT,
            "devices",
            ["device_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(CONSTRAINT, type_="foreignkey")
        batch.drop_index("ix_ip_addresses_device_id")
        batch.drop_column("device_id")
