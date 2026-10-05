"""Web routes for device management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cmdb import CMDB_SELECTS, SEARCH_COLUMNS, cmdb_errors, options
from app.database import get_db
from app.models import Device, User
from app.schemas import DeviceCreate, DeviceUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, list_field_values, model_to_form

router = APIRouter()


def _form_context(db: Session, form_data: dict, item: Device | None = None) -> dict:
    """Shared context for the add/edit device form."""
    devices = db.scalars(select(Device).order_by(Device.hostname)).all()
    parent_options = [("", "— none (top-level) —")] + [
        (device.id, f"{device.hostname}" + (f" · {device.asset_tag}" if device.asset_tag else ""))
        for device in devices
        if item is None or device.id != item.id
    ]
    return {
        "cmdb_selects": {name: options(values) for name, values in CMDB_SELECTS.items()},
        "parent_options": parent_options,
        "mac_values": list_field_values(form_data, "mac_addresses"),
    }


def _apply(device: Device, payload) -> None:
    for key, value in payload.model_dump().items():
        setattr(device, key, value)


@router.get("/devices", name="devices")
async def devices_page(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    query = select(Device)
    term = request.query_params.get("q", "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.where(or_(*(column.ilike(pattern) for column in SEARCH_COLUMNS)))
    status = request.query_params.get("status", "").strip()
    if status:
        query = query.where(Device.status == status)
    lifecycle = request.query_params.get("lifecycle", "").strip()
    if lifecycle:
        query = query.where(Device.lifecycle_status == lifecycle)

    devices = db.scalars(query.order_by(Device.hostname)).all()
    return render(request, "devices/list.html", {
        "active": "devices",
        "items": devices,
        "q": term,
        "status_filter": status,
        "lifecycle_filter": lifecycle,
        "statuses": options(("Active", "Inactive", "Maintenance")),
        "lifecycles": options(CMDB_SELECTS["lifecycle_status"]),
    })


@router.get("/devices/add", name="devices_add", dependencies=[Depends(require_admin_web)])
async def add_device_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "devices/form.html", {
        "active": "devices", "mode": "add", "form_data": {},
        **_form_context(db, {}),
    })


@router.post("/devices/add", name="devices_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_device_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    # clean_form needs the raw FormData: it has getlist(), which is the only way
    # to see every row of the repeatable MAC inputs.
    form_data = clean_form(form)
    context = _form_context(db, form_data)
    try:
        payload = DeviceCreate.model_validate(form_data)
    except ValidationError as exc:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "add", "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()], **context,
        })

    errors = cmdb_errors(db, payload, None)
    if errors:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "add", "form_data": form_data,
            "errors": errors, **context,
        })

    device = Device(**payload.model_dump())
    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent admin claiming the same asset tag.
        db.rollback()
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "add", "form_data": form_data,
            "errors": ["Asset tag is already used by another device."], **context,
        })
    return redirect("/devices", f"Device {device.hostname} added successfully.")


@router.get("/devices/{item_id}/edit", name="devices_edit", dependencies=[Depends(require_admin_web)])
async def edit_device_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    device = db.get(Device, item_id)
    if device is None:
        raise HTTPException(status_code=404)
    form_data = model_to_form(device)
    return render(request, "devices/form.html", {
        "active": "devices", "mode": "edit", "item": device, "form_data": form_data,
        **_form_context(db, form_data, device),
    })


@router.post("/devices/{item_id}/edit", name="devices_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_device_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    device = db.get(Device, item_id)
    if device is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = clean_form(form)
    context = _form_context(db, form_data, device)
    try:
        payload = DeviceUpdate.model_validate(form_data)
    except ValidationError as exc:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "edit", "item": device, "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()], **context,
        })

    errors = cmdb_errors(db, payload, item_id)
    if errors:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "edit", "item": device, "form_data": form_data,
            "errors": errors, **context,
        })

    _apply(device, payload)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "edit", "item": device, "form_data": form_data,
            "errors": ["Asset tag is already used by another device."], **context,
        })
    return redirect("/devices", f"Device {device.hostname} updated successfully.")


@router.post("/devices/{item_id}/delete", name="devices_delete",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def delete_device(item_id: int, request: Request, db: Session = Depends(get_db)):
    device = db.get(Device, item_id)
    if device is None:
        raise HTTPException(status_code=404)
    db.delete(device)
    db.commit()
    return redirect("/devices", f"Device {device.hostname} deleted successfully.")