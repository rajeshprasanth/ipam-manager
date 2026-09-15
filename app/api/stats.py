"""REST API routes for dashboard statistics."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_api
from app.models import Device, IPAddress, Network, User

router = APIRouter()


@router.get("/stats", name="api_stats")
async def stats(db: Session = Depends(get_db), _: User = Depends(get_current_user_api)):
    total = db.scalar(select(func.count()).select_from(IPAddress)) or 0
    status_counts = dict(db.execute(
        select(IPAddress.status, func.count()).group_by(IPAddress.status)
    ).all())

    return {
        "ip_stats": {
            "total": total,
            "available": status_counts.get("Available", 0),
            "reserved": status_counts.get("Reserved", 0),
            "active": status_counts.get("Active", 0),
            "deprecated": status_counts.get("Deprecated", 0),
        },
        "network_count": db.scalar(select(func.count()).select_from(Network)) or 0,
        "device_count": db.scalar(select(func.count()).select_from(Device)) or 0,
        "user_count": db.scalar(select(func.count()).select_from(User)) or 0,
    }