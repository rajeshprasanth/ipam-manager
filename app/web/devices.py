"""Web routes for device management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, User
from app.schemas import DeviceCreate, DeviceUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, model_to_form

router = APIRouter()


@router.get("/devices", name="devices")
async def devices_page(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    devices = db.scalars(select(Device).order_by(Device.hostname)).all()
    return render(request, "devices/list.html", {"active": "devices", "items": devices})


@router.get("/devices/add", name="devices_add", dependencies=[Depends(require_admin_web)])
async def add_device_page(request: Request):
    return render(request, "devices/form.html", {"active": "devices", "mode": "add", "form_data": {}})


@router.post("/devices/add", name="devices_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_device_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)
    try:
        payload = DeviceCreate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "add", "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    return redirect("/devices", f"Device {device.hostname} added successfully.")


@router.get("/devices/{item_id}/edit", name="devices_edit", dependencies=[Depends(require_admin_web)])
async def edit_device_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    device = db.get(Device, item_id)
    if device is None:
        raise HTTPException(status_code=404)
    return render(request, "devices/form.html", {
        "active": "devices", "mode": "edit", "item": device, "form_data": model_to_form(device),
    })


@router.post("/devices/{item_id}/edit", name="devices_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_device_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    device = db.get(Device, item_id)
    if device is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = dict(form)
    try:
        payload = DeviceUpdate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "devices/form.html", {
            "active": "devices", "mode": "edit", "item": device, "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    for key, value in payload.model_dump().items():
        setattr(device, key, value)
    db.commit()
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