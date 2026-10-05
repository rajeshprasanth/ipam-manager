"""Shared CMDB vocabulary and referential checks for devices.

The web form and the REST API validate configuration items identically, so the
controlled vocabularies, search columns and referential rules live here instead
of being duplicated per route module.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ANTIVIRUS_STATUSES,
    BACKUP_STATUSES,
    COMPLIANCE_STATUSES,
    CRITICALITY_LEVELS,
    DATA_CLASSIFICATIONS,
    DEVICE_CLASSES,
    DISCOVERY_SOURCES,
    LIFECYCLE_STATUSES,
    PATCH_STATUSES,
    Device,
)

# Rendered as dropdowns; values mirror the Literal types in app/schemas.py.
CMDB_SELECTS: dict[str, tuple[str, ...]] = {
    "device_class": DEVICE_CLASSES,
    "lifecycle_status": LIFECYCLE_STATUSES,
    "criticality": CRITICALITY_LEVELS,
    "data_classification": DATA_CLASSIFICATIONS,
    "compliance_status": COMPLIANCE_STATUSES,
    "patch_status": PATCH_STATUSES,
    "antivirus_status": ANTIVIRUS_STATUSES,
    "backup_status": BACKUP_STATUSES,
    "discovery_source": DISCOVERY_SOURCES,
}

# Columns the inventory search box scans.
SEARCH_COLUMNS = (
    Device.hostname, Device.fqdn, Device.asset_tag, Device.inventory_id,
    Device.serial_number, Device.barcode, Device.instance_id, Device.site_code,
)


def options(values) -> list[tuple[str, str]]:
    """Turn a vocabulary into (value, label) pairs for a select element."""
    return [(value, value) for value in values]


def cmdb_errors(db: Session, payload, item_id: int | None = None) -> list[str]:
    """Referential rules the column types cannot express.

    ``item_id`` is the device being edited, or None when creating one. Returns
    human-readable messages; callers decide whether to re-render a form or raise
    an HTTP error.
    """
    errors: list[str] = []

    # asset_tag is the CMDB's canonical key, backed by a unique index.
    if payload.asset_tag:
        stmt = select(Device.id).where(func.lower(Device.asset_tag) == payload.asset_tag.lower())
        if item_id is not None:
            stmt = stmt.where(Device.id != item_id)
        if db.scalar(stmt) is not None:
            errors.append(f"Asset tag '{payload.asset_tag}' is already used by another device.")

    parent_id = payload.parent_device_id
    if parent_id:
        if item_id is not None and parent_id == item_id:
            errors.append("A device cannot be its own parent device.")
        elif db.get(Device, parent_id) is None:
            errors.append(f"Parent device {parent_id} does not exist.")
        elif item_id is not None:
            # Walk the proposed chain upwards. Seeding `seen` with our own id
            # stops the walk the moment it reaches us, which is exactly the loop
            # we are trying to prevent.
            seen: set[int] = {item_id}
            cursor: Device | None = db.get(Device, parent_id)
            while cursor is not None and cursor.id not in seen:
                seen.add(cursor.id)
                cursor = db.get(Device, cursor.parent_device_id) if cursor.parent_device_id else None
            if cursor is not None and cursor.id == item_id:
                errors.append("That parent would create a circular device hierarchy.")
    return errors