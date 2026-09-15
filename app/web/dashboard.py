"""Dashboard web route."""
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, IPAddress, Network, User
from app.web.deps import get_current_user_web, render

router = APIRouter()


@router.get("/dashboard", name="dashboard")
async def dashboard(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    total_ips = db.scalar(select(func.count()).select_from(IPAddress)) or 0
    status_counts = dict(db.execute(
        select(IPAddress.status, func.count()).group_by(IPAddress.status)
    ).all())

    counts = {
        "total": total_ips,
        "available": status_counts.get("Available", 0),
        "reserved": status_counts.get("Reserved", 0),
        "active": status_counts.get("Active", 0),
        "deprecated": status_counts.get("Deprecated", 0),
    }
    total_networks = db.scalar(select(func.count()).select_from(Network)) or 0
    total_devices = db.scalar(select(func.count()).select_from(Device)) or 0
    total_users = db.scalar(select(func.count()).select_from(User)) or 0

    device_type_rows = db.execute(
        select(IPAddress.device_type, func.count())
        .where(IPAddress.device_type.is_not(None))
        .group_by(IPAddress.device_type)
        .order_by(func.count().desc())
        .limit(6)
    ).all()
    device_type_counts = [{"label": label, "value": value} for label, value in device_type_rows]

    recent_ips = db.scalars(
        select(IPAddress).order_by(IPAddress.updated_at.desc()).limit(6)
    ).all()

    utilization = (counts["active"] / total_ips * 100) if total_ips else 0

    return render(request, "dashboard.html", {
        "active": "dashboard",
        "counts": counts,
        "total_networks": total_networks,
        "total_devices": total_devices,
        "total_users": total_users,
        "utilization": round(utilization, 1),
        "device_type_counts": json.dumps(device_type_counts),
        "status_chart": json.dumps({
            "available": counts["available"],
            "active": counts["active"],
            "reserved": counts["reserved"],
            "deprecated": counts["deprecated"],
        }),
        "recent_ips": recent_ips,
    })