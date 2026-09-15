"""Web routes for network management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Network, User
from app.schemas import NetworkCreate, NetworkUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, model_to_form

router = APIRouter()


@router.get("/networks", name="networks")
async def networks_page(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    networks = db.scalars(select(Network).order_by(Network.network_name)).all()
    return render(request, "networks/list.html", {"active": "networks", "items": networks})


@router.get("/networks/add", name="networks_add", dependencies=[Depends(require_admin_web)])
async def add_network_page(request: Request):
    return render(request, "networks/form.html", {"active": "networks", "mode": "add", "form_data": {}})


@router.post("/networks/add", name="networks_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_network_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)
    try:
        payload = NetworkCreate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "add", "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    dup = db.scalar(select(Network).where(Network.network_range == payload.network_range))
    if dup:
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "add", "form_data": form_data,
            "errors": [f"Network range {payload.network_range} already exists."],
        })

    network = Network(**payload.model_dump())
    db.add(network)
    db.commit()
    return redirect("/networks", f"Network {network.network_name} added successfully.")


@router.get("/networks/{item_id}/edit", name="networks_edit", dependencies=[Depends(require_admin_web)])
async def edit_network_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    network = db.get(Network, item_id)
    if network is None:
        raise HTTPException(status_code=404)
    return render(request, "networks/form.html", {
        "active": "networks", "mode": "edit", "item": network, "form_data": model_to_form(network),
    })


@router.post("/networks/{item_id}/edit", name="networks_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_network_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    network = db.get(Network, item_id)
    if network is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = dict(form)
    try:
        payload = NetworkUpdate.model_validate(clean_form(form_data))
    except ValidationError as exc:
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "edit", "item": network, "form_data": form_data,
            "errors": [err["msg"] for err in exc.errors()],
        })

    dup = db.scalar(select(Network).where(
        Network.network_range == payload.network_range, Network.id != item_id))
    if dup:
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "edit", "item": network, "form_data": form_data,
            "errors": [f"Network range {payload.network_range} already exists."],
        })

    for key, value in payload.model_dump().items():
        setattr(network, key, value)
    db.commit()
    return redirect("/networks", f"Network {network.network_name} updated successfully.")


@router.post("/networks/{item_id}/delete", name="networks_delete",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def delete_network(item_id: int, request: Request, db: Session = Depends(get_db)):
    network = db.get(Network, item_id)
    if network is None:
        raise HTTPException(status_code=404)
    db.delete(network)
    db.commit()
    return redirect("/networks", f"Network {network.network_name} deleted successfully.")