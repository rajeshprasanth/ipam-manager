"""REST API routes for device management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cmdb import cmdb_errors
from app.database import get_db
from app.deps import get_current_user_api, require_admin_api
from app.models import Device, User
from app.schemas import DeviceCreate, DeviceOut, DeviceUpdate

router = APIRouter()


@router.get("", response_model=list[DeviceOut], name="api_devices_list")
async def list_devices(db: Session = Depends(get_db), _: User = Depends(get_current_user_api)):
    return db.scalars(select(Device).order_by(Device.hostname)).all()


@router.get("/{item_id}", response_model=DeviceOut, name="api_devices_get")
async def get_device(item_id: int, db: Session = Depends(get_db),
                     _: User = Depends(get_current_user_api)):
    item = db.get(Device, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return item


@router.post("", response_model=DeviceOut, status_code=201, name="api_devices_create")
async def create_device(payload: DeviceCreate, db: Session = Depends(get_db),
                        _: User = Depends(require_admin_api)):
    errors = cmdb_errors(db, payload)
    if errors:
        raise HTTPException(status_code=409, detail=errors)
    item = Device(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=["Asset tag is already used by another device."])
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=DeviceOut, name="api_devices_update")
async def update_device(item_id: int, payload: DeviceUpdate, db: Session = Depends(get_db),
                        _: User = Depends(require_admin_api)):
    item = db.get(Device, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    errors = cmdb_errors(db, payload, item_id)
    if errors:
        raise HTTPException(status_code=409, detail=errors)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=["Asset tag is already used by another device."])
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, name="api_devices_delete")
async def delete_device(item_id: int, db: Session = Depends(get_db),
                        _: User = Depends(require_admin_api)):
    item = db.get(Device, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(item)
    db.commit()