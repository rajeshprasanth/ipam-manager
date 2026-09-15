"""REST API routes for network management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_api, require_admin_api
from app.models import Network, User
from app.schemas import NetworkCreate, NetworkOut, NetworkUpdate

router = APIRouter()


@router.get("", response_model=list[NetworkOut], name="api_networks_list")
async def list_networks(db: Session = Depends(get_db), _: User = Depends(get_current_user_api)):
    return db.scalars(select(Network).order_by(Network.network_name)).all()


@router.get("/{item_id}", response_model=NetworkOut, name="api_networks_get")
async def get_network(item_id: int, db: Session = Depends(get_db),
                      _: User = Depends(get_current_user_api)):
    item = db.get(Network, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Network not found")
    return item


@router.post("", response_model=NetworkOut, status_code=201, name="api_networks_create")
async def create_network(payload: NetworkCreate, db: Session = Depends(get_db),
                         _: User = Depends(require_admin_api)):
    if db.scalar(select(Network).where(Network.network_range == payload.network_range)):
        raise HTTPException(status_code=409, detail="Network range already exists")
    item = Network(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=NetworkOut, name="api_networks_update")
async def update_network(item_id: int, payload: NetworkUpdate, db: Session = Depends(get_db),
                         _: User = Depends(require_admin_api)):
    item = db.get(Network, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Network not found")
    if payload.network_range and db.scalar(select(Network).where(
            Network.network_range == payload.network_range, Network.id != item_id)):
        raise HTTPException(status_code=409, detail="Network range already exists")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, name="api_networks_delete")
async def delete_network(item_id: int, db: Session = Depends(get_db),
                         _: User = Depends(require_admin_api)):
    item = db.get(Network, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Network not found")
    db.delete(item)
    db.commit()