"""Dashboard web route."""
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import IPAddress, User
from app.stats import dashboard_stats
from app.web.deps import get_current_user_web, render

router = APIRouter()


@router.get("/dashboard", name="dashboard")
async def dashboard(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    stats = dashboard_stats(db)
    counts = {"total": stats["total_ips"], **stats["ip_status"]}

    device_type_rows = db.execute(
        select(IPAddress.device_type, func.count())
        .where(IPAddress.device_type.is_not(None))
        .group_by(IPAddress.device_type)
        .order_by(func.count().desc())
        .limit(6)
    ).all()
    device_type_counts = [{"label": label, "value": value} for label, value in device_type_rows]

    recent_ips = db.scalars(
        select(IPAddress).options(selectinload(IPAddress.device))
        .order_by(IPAddress.updated_at.desc()).limit(6)
    ).all()

    utilization = (counts["active"] / counts["total"] * 100) if counts["total"] else 0

    return render(request, "dashboard.html", {
        "active": "dashboard",
        "counts": counts,
        "total_networks": stats["total_networks"],
        "total_users": stats["total_users"],
        "total_devices": stats["total_devices"],
        "device_counts": stats["device_status"],
        "assigned_ips": stats["assigned_ips"],
        "unassigned_ips": stats["unassigned_ips"],
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
