"""Web routes for network management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.ipam import (
    IPAM_SELECTS,
    NETWORK_SEARCH_COLUMNS,
    ipam_options,
    network_errors,
    search_filter,
)

# (value, label) pairs for every network dropdown, built once.
IPAM_OPTIONS = {key: ipam_options(values) for key, values in IPAM_SELECTS.items()}
from app.models import Network, User
from app.schemas import NetworkCreate, NetworkUpdate
from app.web.deps import get_current_user_web, redirect, render, require_admin_web, verify_csrf
from app.web.forms import clean_form, list_field_values, model_to_form

router = APIRouter()


def _parent_choices(db: Session, exclude_id: int | None = None) -> list[tuple[int, str]]:
    """Networks available as a supernet for the parent_network_id dropdown."""
    stmt = select(Network).order_by(Network.network_name)
    if exclude_id is not None:
        stmt = stmt.where(Network.id != exclude_id)
    return [
        (network.id, f"{network.network_name} ({network.network_range})")
        for network in db.scalars(stmt).all()
    ]


@router.get("/networks", name="networks")
async def networks_page(request: Request, _: User = Depends(get_current_user_web), db: Session = Depends(get_db)):
    q = request.query_params.get("q", "").strip()
    env = request.query_params.get("environment", "").strip()
    status = request.query_params.get("status", "").strip()

    stmt = select(Network)
    if q:
        stmt = stmt.where(search_filter(NETWORK_SEARCH_COLUMNS, q))
    if env:
        stmt = stmt.where(Network.environment == env)
    if status:
        stmt = stmt.where(Network.status == status)

    # The cards render the address count and parent name, so load both up front.
    networks = db.scalars(
        stmt.options(selectinload(Network.ip_addresses), selectinload(Network.parent_network))
        .order_by(Network.network_name)
    ).all()
    return render(request, "networks/list.html", {
        "active": "networks", "items": networks, "q": q, "flt_env": env, "flt_status": status,
        "environments": IPAM_OPTIONS["environment"],
        "statuses": IPAM_OPTIONS["status"],
    })


@router.get("/networks/add", name="networks_add", dependencies=[Depends(require_admin_web)])
async def add_network_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "networks/form.html", {
        "active": "networks", "mode": "add", "form_data": {},
        "parents": _parent_choices(db), "options": IPAM_OPTIONS,
    })


@router.post("/networks/add", name="networks_add_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def add_network_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)

    def reject(errors):
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "add", "form_data": form_data, "errors": errors,
            "parents": _parent_choices(db), "options": IPAM_OPTIONS,
            "dns_rows": list_field_values(form_data, "dns_servers"),
        })

    try:
        payload = NetworkCreate.model_validate(clean_form(form))
    except ValidationError as exc:
        return reject([err["msg"] for err in exc.errors()])

    errors = network_errors(db, payload)
    if errors:
        return reject(errors)

    network = Network(**payload.model_dump())
    db.add(network)
    db.commit()
    return redirect("/networks", f"Network {network.network_name} added successfully.")


@router.get("/networks/{item_id}/edit", name="networks_edit", dependencies=[Depends(require_admin_web)])
async def edit_network_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    network = db.get(Network, item_id)
    if network is None:
        raise HTTPException(status_code=404)
    form_data = model_to_form(network)
    return render(request, "networks/form.html", {
        "active": "networks", "mode": "edit", "item": network, "form_data": form_data,
        "parents": _parent_choices(db, exclude_id=item_id), "options": IPAM_OPTIONS,
        "dns_rows": list_field_values(form_data, "dns_servers"),
    })


@router.post("/networks/{item_id}/edit", name="networks_edit_post",
             dependencies=[Depends(verify_csrf), Depends(require_admin_web)])
async def edit_network_submit(item_id: int, request: Request, db: Session = Depends(get_db)):
    network = db.get(Network, item_id)
    if network is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    form_data = dict(form)

    def reject(errors):
        return render(request, "networks/form.html", {
            "active": "networks", "mode": "edit", "item": network, "form_data": form_data,
            "errors": errors, "parents": _parent_choices(db, exclude_id=item_id),
            "options": IPAM_OPTIONS, "dns_rows": list_field_values(form_data, "dns_servers"),
        })

    try:
        payload = NetworkUpdate.model_validate(clean_form(form))
    except ValidationError as exc:
        return reject([err["msg"] for err in exc.errors()])

    errors = network_errors(db, payload, item_id=item_id)
    if errors:
        return reject(errors)

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