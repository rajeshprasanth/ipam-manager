"""Shared aggregate queries for the dashboard and the stats API."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, IPAddress, Network, User


def _status_counts(db: Session, column) -> dict[str, int]:
    """Count rows per status value for a model column."""
    return dict(db.execute(select(column, func.count()).group_by(column)).all())


def dashboard_stats(db: Session) -> dict:
    """Collect every figure shown on the dashboard.

    Returns counts keyed by ``ip_status``, ``device_status`` and totals, so the
    web dashboard and ``GET /api/stats`` stay in sync.
    """
    total_ips = db.scalar(select(func.count()).select_from(IPAddress)) or 0
    ip_status = _status_counts(db, IPAddress.status)
    device_status = _status_counts(db, Device.status)
    assigned_ips = db.scalar(
        select(func.count()).select_from(IPAddress).where(IPAddress.device_id.is_not(None))
    ) or 0

    return {
        "total_ips": total_ips,
        "ip_status": {
            "available": ip_status.get("Available", 0),
            "reserved": ip_status.get("Reserved", 0),
            "active": ip_status.get("Active", 0),
            "deprecated": ip_status.get("Deprecated", 0),
        },
        "total_devices": db.scalar(select(func.count()).select_from(Device)) or 0,
        "device_status": {
            "active": device_status.get("Active", 0),
            "inactive": device_status.get("Inactive", 0),
            "maintenance": device_status.get("Maintenance", 0),
        },
        "total_networks": db.scalar(select(func.count()).select_from(Network)) or 0,
        "total_users": db.scalar(select(func.count()).select_from(User)) or 0,
        "assigned_ips": assigned_ips,
        "unassigned_ips": total_ips - assigned_ips,
    }
