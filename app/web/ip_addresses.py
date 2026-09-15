"""Web routes for IP address management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IPAddress, IPHistory, User
from app.schemas import IPAddressCreate, IPAddressUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, model_to_form

router = APIRouter()
PAGE_SIZE = 20


def _filters(request: Request):
    """Build filtering conditions shared by the list route."""
    criteria = []
    search = request.query_params.get("search", "").strip()
    status = request.query_params.get("status", "").strip()
    device_type = request.query_params.get("device_type", "").strip()
    vlan_raw = request.query_params.get("vlan_id", "").strip()

    if search:
        like = f"%{search}%"
        criteria.append(or_(
            IPAddress.ip_address.ilike(like),
            IPAddress.hostname.ilike(like),
            IPAddress.assigned_to.ilike(like),
            IPAddress.description.ilike(like),
            IPAddress.fqdn.ilike(like),
        ))
    if status:
        criteria.append(IPAddress.status == status)
    if device_type:
        criteria.append(IPAddress.device_type == device_type)
    if vlan_raw:
        criteria.append(IPAddress.vlan_id == int(vlan_raw))

    return {
        "search": search,
        "status": status,
        "device_type": device_type,
        "vlan_id": vlan_raw,
        "criteria": criteria,
    }


@router.get("/ip-addresses", name="ip_addresses")
async def ip_addresses_page(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except ValueError:
        page = 1

    filters = _filters(request)
    statement = select(IPAddress)
    if filters["criteria"]:
        statement = statement.where(*filters["criteria"])

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)

    items = db.scalars(
        statement.order_by(IPAddress.ip_address).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()

    return render(request, "ip_addresses/list.html", {
        "active": "ip_addresses",
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
        **{k: v for k, v in filters.items() if k != "criteria"},
    })


def _history(db: Session, ip: IPAddress, reason: str, user: User | None) -> None:
    db.add(IPHistory(
        ip_address=ip.ip_address,
        ip_id=ip.id,
        previous_hostname=ip.hostname,
        previous_assigned_to=ip.assigned_to,
        previous_status=ip.status,
        change_reason=reason,
        changed_by=user.username if user else None,
    ))


@router.get("/ip-addresses/add", name="ip_addresses_add", dependencies=[Depends(require_admin_web)])
async def add_ip_page(request: Request):
    return render(request, "ip_addresses/form.html", {
        "active": "ip_addresses", "mode": "add", "form_data": {},
    })


@router.post("/ip-addresses/add", name="ip_addresses_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_ip_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)
    try:
        payload = IPAddressCreate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "ip_addresses/form.html", {
            "active": "ip_addresses", "mode": "add", "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    if db.scalar(select(IPAddress).where(IPAddress.ip_address == payload.ip_address)):
        return render(request, "ip_addresses/form.html", {
            "active": "ip_addresses", "mode": "add", "form_data": form_data,
            "errors": [f"IP address {payload.ip_address} already exists."],
        })

    ip = IPAddress(**payload.model_dump())
    _history(db, ip, "Created via web interface", request.state.user)
    db.add(ip)
    db.commit()
    return redirect("/ip-addresses", f"IP address {ip.ip_address} added successfully.")


@router.get("/ip-addresses/{item_id}/edit", name="ip_addresses_edit", dependencies=[Depends(require_admin_web)])
async def edit_ip_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, item_id)
    if ip is None:
        raise HTTPException(status_code=404)
    return render(request, "ip_addresses/form.html", {
        "active": "ip_addresses", "mode": "edit", "item": ip, "form_data": model_to_form(ip),
    })


@router.post("/ip-addresses/{item_id}/edit", name="ip_addresses_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_ip_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, item_id)
    if ip is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = dict(form)
    try:
        payload = IPAddressUpdate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "ip_addresses/form.html", {
            "active": "ip_addresses", "mode": "edit", "item": ip, "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    new_ip = payload.ip_address
    if new_ip and db.scalar(select(IPAddress).where(IPAddress.ip_address == new_ip, IPAddress.id != item_id)):
        return render(request, "ip_addresses/form.html", {
            "active": "ip_addresses", "mode": "edit", "item": ip, "form_data": form_data,
            "errors": [f"IP address {new_ip} already exists."],
        })

    _history(db, ip, "Updated via web interface", request.state.user)
    for key, value in payload.model_dump().items():
        setattr(ip, key, value)
    db.commit()
    return redirect("/ip-addresses", f"IP address {ip.ip_address} updated successfully.")


@router.post("/ip-addresses/{item_id}/delete", name="ip_addresses_delete",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def delete_ip(item_id: int, request: Request, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, item_id)
    if ip is None:
        raise HTTPException(status_code=404)
    _history(db, ip, "Deleted via web interface", request.state.user)
    db.delete(ip)
    db.commit()
    return redirect("/ip-addresses", f"IP address {ip.ip_address} deleted successfully.")