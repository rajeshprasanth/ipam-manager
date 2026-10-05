"""REST API routes for IP address management."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_api, require_admin_api
from app.ipam import ip_address_errors, ip_search_columns, network_subnet_id_for_address, search_filter
from app.models import Device, IPAddress, User
from app.schemas import IPAddressCreate, IPAddressOut, IPAddressUpdate

router = APIRouter()


def _check_device(db: Session, device_id: int | None) -> None:
    """Reject a device_id that does not resolve, so the FK never blows up later."""
    if device_id is not None and db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")


@router.get("", response_model=dict, name="api_ip_addresses_list")
async def list_ip_addresses(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user_api),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    device_id: int | None = Query(default=None, ge=1),
    subnet_id: int | None = Query(default=None, ge=1),
    vlan_id: int | None = Query(default=None),
    is_primary: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    statement = select(IPAddress)
    if search:
        statement = statement.where(search_filter(ip_search_columns(), search))
    if status:
        statement = statement.where(IPAddress.status == status)
    if device_type:
        statement = statement.where(IPAddress.device_type == device_type)
    if device_id is not None:
        statement = statement.where(IPAddress.device_id == device_id)
    if subnet_id is not None:
        statement = statement.where(IPAddress.subnet_id == subnet_id)
    if is_primary is not None:
        statement = statement.where(IPAddress.is_primary.is_(is_primary))
    if vlan_id is not None:
        statement = statement.where(IPAddress.vlan_id == vlan_id)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    pages = max(1, (total + per_page - 1) // per_page)
    items = db.scalars(
        statement.order_by(IPAddress.ip_address).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return {
        "items": [IPAddressOut.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{item_id}", response_model=IPAddressOut, name="api_ip_addresses_get")
async def get_ip_address(item_id: int, db: Session = Depends(get_db),
                         _: User = Depends(get_current_user_api)):
    item = db.get(IPAddress, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    return item


@router.post("", response_model=IPAddressOut, status_code=201, name="api_ip_addresses_create")
async def create_ip_address(payload: IPAddressCreate, db: Session = Depends(get_db),
                            _: User = Depends(require_admin_api)):
    if db.scalar(select(IPAddress).where(IPAddress.ip_address == payload.ip_address)):
        raise HTTPException(status_code=409, detail="IP address already exists")
    _check_device(db, payload.device_id)
    errors = ip_address_errors(db, payload)
    if errors:
        raise HTTPException(status_code=409, detail="; ".join(errors))
    values = payload.model_dump()
    if not values.get("subnet_id"):
        # Link the address to the subnet that contains it when none was given.
        values["subnet_id"] = network_subnet_id_for_address(db, payload.ip_address)
    item = IPAddress(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=IPAddressOut, name="api_ip_addresses_update")
async def update_ip_address(item_id: int, payload: IPAddressUpdate, db: Session = Depends(get_db),
                            _: User = Depends(require_admin_api)):
    item = db.get(IPAddress, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    if payload.ip_address and db.scalar(select(IPAddress).where(
            IPAddress.ip_address == payload.ip_address,             IPAddress.id != item_id)):
        raise HTTPException(status_code=409, detail="IP address already exists")
    _check_device(db, payload.device_id)
    # A PATCH is partial, so merge over the stored row before validating:
    # otherwise a lone {"is_primary": true} would be checked without the
    # device it belongs to and the one-primary rule would be skipped.
    merged = {column.name: getattr(item, column.name) for column in IPAddress.__table__.columns}
    merged.update(payload.model_dump(exclude_unset=True))
    errors = ip_address_errors(db, IPAddressUpdate.model_validate(merged), item_id=item_id)
    if errors:
        raise HTTPException(status_code=409, detail="; ".join(errors))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, name="api_ip_addresses_delete")
async def delete_ip_address(item_id: int, db: Session = Depends(get_db),
                            _: User = Depends(require_admin_api)):
    item = db.get(IPAddress, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    db.delete(item)
    db.commit()