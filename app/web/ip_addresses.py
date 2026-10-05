"""Web routes for IP address management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.ipam import (
    IPAM_SELECTS,
    ip_address_errors,
    ip_search_columns,
    ipam_options,
    network_subnet_id_for_address,
    search_filter,
)
from app.models import Device, IPAddress, IPHistory, Network, User
from app.schemas import IPAddressCreate, IPAddressUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, model_to_form

IPAM_OPTIONS = {key: ipam_options(values) for key, values in IPAM_SELECTS.items()}

router = APIRouter()
PAGE_SIZE = 20


def _device_options(db: Session) -> list[tuple[int, str]]:
    """Devices offered in the IP address form, grouped by status for scanning."""
    devices = db.scalars(select(Device).order_by(Device.hostname)).all()
    return [(device.id, f"{device.hostname} ({device.status})") for device in devices]


def _subnet_options(db: Session, exclude_id: int | None = None) -> list[tuple[int, str]]:
    """Subnets offered in the IP address form."""
    stmt = select(Network).order_by(Network.network_name)
    if exclude_id is not None:
        stmt = stmt.where(Network.id != exclude_id)
    return [
        (network.id, f"{network.network_name} ({network.network_range})")
        for network in db.scalars(stmt).all()
    ]


def _form_context(db: Session, **context) -> dict:
    """Shared render payload for the add/edit form."""
    return {
        "active": "ip_addresses",
        "device_options": _device_options(db),
        "subnet_options": _subnet_options(db),
        "options": IPAM_OPTIONS,
        **context,
    }


def _unknown_device(db: Session, device_id: int | None) -> bool:
    """True when a submitted device_id does not resolve to a real device."""
    if device_id is None:
        return False
    return db.get(Device, device_id) is None


def _filters(request: Request):
    """Build filtering conditions shared by the list route."""
    criteria = []
    search = request.query_params.get("search", "").strip()
    status = request.query_params.get("status", "").strip()
    device_type = request.query_params.get("device_type", "").strip()
    vlan_raw = request.query_params.get("vlan_id", "").strip()
    device_raw = request.query_params.get("device_id", "").strip()
    subnet_raw = request.query_params.get("subnet_id", "").strip()

    if search:
        criteria.append(search_filter(ip_search_columns(), search))
    if status:
        criteria.append(IPAddress.status == status)
    if device_type:
        criteria.append(IPAddress.device_type == device_type)
    if vlan_raw:
        criteria.append(IPAddress.vlan_id == int(vlan_raw))
    if device_raw:
        criteria.append(IPAddress.device_id == int(device_raw))
    if subnet_raw:
        criteria.append(IPAddress.subnet_id == int(subnet_raw))

    return {
        "search": search,
        "status": status,
        "device_type": device_type,
        "vlan_id": vlan_raw,
        "device_id": device_raw,
        "subnet_id": subnet_raw,
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
        statement.options(selectinload(IPAddress.device), selectinload(IPAddress.subnet))
        .order_by(IPAddress.ip_address)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()

    return render(request, "ip_addresses/list.html", {
        "active": "ip_addresses",
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
        "devices": _device_options(db),
        "subnets": _subnet_options(db),
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
async def add_ip_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "ip_addresses/form.html",
                  _form_context(db, mode="add", form_data={}))


@router.post("/ip-addresses/add", name="ip_addresses_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_ip_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = clean_form(form)
    try:
        payload = IPAddressCreate.model_validate(form_data)
    except ValidationError as exc:
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="add", form_data=form_data, errors=[err["msg"] for err in exc.errors()]))

    if db.scalar(select(IPAddress).where(IPAddress.ip_address == payload.ip_address)):
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="add", form_data=form_data,
            errors=[f"IP address {payload.ip_address} already exists."]))

    errors = list(ip_address_errors(db, payload))
    if _unknown_device(db, payload.device_id):
        errors.append(f"Device {payload.device_id} does not exist.")
    if errors:
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="add", form_data=form_data, errors=errors))

    values = payload.model_dump()
    if not values.get("subnet_id"):
        # No subnet chosen: fall back to the one that contains the address so
        # the inventory links up without the operator hunting for it.
        values["subnet_id"] = network_subnet_id_for_address(db, payload.ip_address)

    ip = IPAddress(**values)
    _history(db, ip, "Created via web interface", request.state.user)
    db.add(ip)
    db.commit()
    return redirect("/ip-addresses", f"IP address {ip.ip_address} added successfully.")


@router.get("/ip-addresses/{item_id}/edit", name="ip_addresses_edit", dependencies=[Depends(require_admin_web)])
async def edit_ip_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, item_id)
    if ip is None:
        raise HTTPException(status_code=404)
    return render(request, "ip_addresses/form.html", _form_context(
        db, mode="edit", item=ip, form_data=model_to_form(ip)))


@router.post("/ip-addresses/{item_id}/edit", name="ip_addresses_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_ip_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, item_id)
    if ip is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = clean_form(form)
    try:
        payload = IPAddressUpdate.model_validate(form_data)
    except ValidationError as exc:
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="edit", item=ip, form_data=form_data,
            errors=[err["msg"] for err in exc.errors()]))

    new_ip = payload.ip_address
    if new_ip and db.scalar(select(IPAddress).where(IPAddress.ip_address == new_ip, IPAddress.id != item_id)):
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="edit", item=ip, form_data=form_data,
            errors=[f"IP address {new_ip} already exists."]))

    errors = list(ip_address_errors(db, payload, item_id=item_id))
    if _unknown_device(db, payload.device_id):
        errors.append(f"Device {payload.device_id} does not exist.")
    if errors:
        return render(request, "ip_addresses/form.html", _form_context(
            db, mode="edit", item=ip, form_data=form_data, errors=errors))

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