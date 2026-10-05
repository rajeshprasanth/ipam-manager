"""REST API routes for dashboard statistics."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_api
from app.models import User
from app.stats import dashboard_stats

router = APIRouter()


@router.get("/stats", name="api_stats")
async def stats(db: Session = Depends(get_db), _: User = Depends(get_current_user_api)):
    figures = dashboard_stats(db)
    return {
        "ip_stats": {"total": figures["total_ips"], **figures["ip_status"]},
        "device_stats": {"total": figures["total_devices"], **figures["device_status"]},
        "network_count": figures["total_networks"],
        "device_count": figures["total_devices"],
        "user_count": figures["total_users"],
        "assigned_ip_count": figures["assigned_ips"],
        "unassigned_ip_count": figures["unassigned_ips"],
    }
