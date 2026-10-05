"""Shared IPAM checks for networks and IP addresses.

Same idea as app/cmdb.py: the web form and the REST API must agree on what a
valid subnet or allocation looks like, so the vocabulary, search columns and the
rules that need a database live in one place.

Two kinds of rule end up here:

* containment and ordering that would need the CIDR parsed anyway -- cheap, and
  done in the schema where the message reaches the user directly;
* rules that need a query: overlapping subnets, a missing parent network, an
  address that does not belong to its declared subnet, and the single-primary
  rule for a multi-homed device.
"""
import ipaddress

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.models import (
    ADDRESS_FAMILIES,
    ALLOCATION_METHODS,
    CRITICALITY_LEVELS,
    NETWORK_ENVIRONMENTS,
    NETWORK_STATUSES,
    IPAddress,
    Network,
)

IPAM_SELECTS: dict[str, tuple[str, ...]] = {
    "address_family": ADDRESS_FAMILIES,
    "environment": NETWORK_ENVIRONMENTS,
    "status": NETWORK_STATUSES,
    "criticality": CRITICALITY_LEVELS,
    "allocation_method": ALLOCATION_METHODS,
}

NETWORK_SEARCH_COLUMNS = (
    Network.network_name, Network.network_range, Network.cidr, Network.vlan_name,
    Network.vrf, Network.domain_name, Network.tenant, Network.owner,
    Network.site_code, Network.datacenter, Network.gateway, Network.tags,
)


def ipam_options(values) -> list[tuple[str, str]]:
    """Turn a vocabulary into (value, label) pairs for a select element."""
    return [(value, value) for value in values]


def parse_network(cidr: str | None):
    """Parse a CIDR block, returning None when it is absent or unusable."""
    if not cidr:
        return None
    try:
        return ipaddress.ip_network(str(cidr), strict=False)
    except ValueError:
        return None


def hierarchy_relatives(db: Session, parent_id: int | None, exclude_id: int | None = None) -> set[int]:
    """Ids of a network's ancestors and descendants, plus the parent itself.

    A supernet and the subnets carved out of it overlap by definition, so the
    overlap check has to exempt them; only the hierarchy decides which nesting
    is legitimate.
    """
    relatives: set[int] = set()
    if not parent_id:
        return relatives

    # Walk up to the root.
    cursor = db.get(Network, parent_id)
    seen: set[int] = set()
    while cursor is not None and cursor.id not in seen:
        seen.add(cursor.id)
        relatives.add(cursor.id)
        cursor = db.get(Network, cursor.parent_network_id) if cursor.parent_network_id else None

    # Walk down through every descendant.
    frontier = [parent_id]
    while frontier:
        current = frontier.pop()
        for child in db.scalars(select(Network).where(Network.parent_network_id == current)).all():
            if child.id not in relatives:
                relatives.add(child.id)
                frontier.append(child.id)

    relatives.discard(exclude_id)
    return relatives


def overlapping_networks(db: Session, cidr: str | None, exclude_id: int | None = None,
                         exempt_ids: set[int] | None = None) -> list[Network]:
    """Every network whose CIDR intersects the proposed one.

    Two blocks overlap when either contains the other; adjacent blocks do not.
    An exact duplicate is therefore just the degenerate case of this check, so
    it replaces the older range-equality test.

    ``exempt_ids`` skips networks whose overlap is already explained by the
    supernet/subnet hierarchy.
    """
    block = parse_network(cidr)
    if block is None:
        return []

    skip = set(exempt_ids or set())
    if exclude_id is not None:
        skip.add(exclude_id)

    candidates = db.scalars(
        select(Network).where(Network.cidr.is_not(None))
    ).all()

    clashes = []
    for other in candidates:
        if other.id in skip:
            continue
        other_block = parse_network(other.cidr)
        if other_block is None or other_block.version != block.version:
            continue
        if block.overlaps(other_block):
            clashes.append(other)
    return clashes


def network_errors(db: Session, payload, item_id: int | None = None) -> list[str]:
    """Referential and topology rules for a network that need a database.

    ``item_id`` is the network being edited, or None when creating one.
    """
    errors: list[str] = []

    dup = db.scalar(select(Network).where(Network.network_range == payload.network_range))
    if dup is not None and (item_id is None or dup.id != item_id):
        errors.append(f"Network range {payload.network_range} already exists.")

    # Nesting a subnet inside its parent is legitimate, so those overlaps are
    # exempt; a parent set later has to include the descendants it adopts.
    parent_id = payload.parent_network_id
    exempt = hierarchy_relatives(db, parent_id, exclude_id=item_id)
    if item_id is not None and db.get(Network, item_id) is not None:
        exempt |= hierarchy_relatives(db, db.get(Network, item_id).parent_network_id,
                                      exclude_id=item_id)

    for clash in overlapping_networks(db, payload.cidr, exclude_id=item_id, exempt_ids=exempt):
        label = clash.network_range or clash.cidr or str(clash.id)
        errors.append(
            f"CIDR {payload.cidr} overlaps {label} "
            f"({clash.network_name or 'unnamed'}). Split or shrink one of them."
        )

    if parent_id:
        if item_id is not None and parent_id == item_id:
            errors.append("A network cannot be its own parent.")
        else:
            parent = db.get(Network, parent_id)
            if parent is None:
                errors.append(f"Parent network {parent_id} does not exist.")
            else:
                parent_block = parse_network(parent.cidr)
                child_block = parse_network(payload.cidr)
                if parent_block and child_block and not child_block.subnet_of(parent_block):
                    errors.append(f"Parent network {parent_id} does not contain this CIDR.")
                if item_id is not None:
                    # Walk upwards; seeding `seen` with our own id catches the loop.
                    seen: set[int] = {item_id}
                    cursor: Network | None = parent
                    while cursor is not None and cursor.id not in seen:
                        seen.add(cursor.id)
                        cursor = (
                            db.get(Network, cursor.parent_network_id)
                            if cursor.parent_network_id else None
                        )
                    if cursor is not None and cursor.id == item_id:
                        errors.append("That parent would create a circular network hierarchy.")

    return errors


def ip_address_errors(db: Session, payload, item_id: int | None = None) -> list[str]:
    """Referential rules for an IP address allocation."""
    errors: list[str] = []

    subnet_id = payload.subnet_id
    if subnet_id:
        subnet = db.get(Network, subnet_id)
        if subnet is None:
            errors.append(f"Subnet {subnet_id} does not exist.")
        else:
            block = parse_network(subnet.cidr)
            if block is not None:
                try:
                    address = ipaddress.ip_address(str(payload.ip_address))
                except ValueError:
                    address = None
                if address is not None:
                    if address.version != block.version:
                        errors.append(
                            f"{payload.ip_address} is not {subnet.address_family}, "
                            f"but subnet {subnet.network_range} is {subnet.address_family}."
                        )
                    elif address not in block:
                        errors.append(
                            f"{payload.ip_address} is outside subnet "
                            f"{subnet.network_range} ({subnet.cidr})."
                        )

    # One management address per device, so a second primary is a conflict.
    if payload.is_primary and payload.device_id:
        stmt = select(IPAddress.id).where(
            IPAddress.device_id == payload.device_id,
            IPAddress.is_primary.is_(True),
        )
        if item_id is not None:
            stmt = stmt.where(IPAddress.id != item_id)
        if db.scalar(stmt) is not None:
            errors.append(
                "That device already has a primary address. "
                "Clear it before assigning another."
            )

    return errors


def network_subnet_id_for_address(db: Session, address: str) -> int | None:
    """Best subnet for an address: the most specific block that contains it."""
    block = None
    try:
        block = ipaddress.ip_address(str(address))
    except ValueError:
        return None
    if block is None:
        return None

    best: tuple[int, int] | None = None
    for network in db.scalars(select(Network).where(Network.cidr.is_not(None))).all():
        candidate = parse_network(network.cidr)
        if candidate is None or candidate.version != block.version:
            continue
        if block in candidate and (best is None or candidate.prefixlen > best[1]):
            best = (network.id, candidate.prefixlen)
    return best[0] if best else None


def ip_search_columns() -> tuple:
    """Columns the IP inventory search box scans.

    ``mac_addresses`` is a JSON array, so it is cast to String before the LIKE
    to keep the search working on both PostgreSQL and SQLite.
    """
    return (
        IPAddress.ip_address,
        IPAddress.fqdn,
        IPAddress.hostname,
        IPAddress.reverse_dns,
        IPAddress.assigned_to,
        cast(IPAddress.mac_addresses, String),
        IPAddress.redundancy_group,
        IPAddress.approved_by,
        IPAddress.tags,
    )


def search_filter(columns: tuple, term: str):
    """Case-insensitive OR across ``columns`` for a search ``term``."""
    like = f"%{term}%"
    return or_(*(column.ilike(like) for column in columns))