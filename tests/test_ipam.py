"""Tests for the IPAM attributes on networks and IP addresses."""
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Device, IPAddress, IPHistory, Network
from tests.conftest import ADMIN_PASSWORD, api_token, login

NETWORK_PAYLOAD = {
    "network_name": "Corporate",
    "network_range": "10.20.0.0/16",
    "cidr": "10.20.0.0/16",
    "subnet_mask": "255.255.0.0",
    "gateway": "10.20.0.1",
    "dns_servers": ["10.20.0.2", "10.20.0.3"],
    "domain_name": "corp.example.com",
    "vrf": "MGMT",
    "environment": "Production",
    "criticality": "High",
    "owner": "Network Team",
    "contact_email": "netops@example.com",
    "cost_center": "CC-1042",
    "site_code": "BLR-01",
    "datacenter": "DC-East",
    "vlan_name": "USERS",
    "vlan_range_start": "10.20.0.1",
    "vlan_range_end": "10.20.255.254",
    "dhcp_enabled": True,
    "dhcp_server": "10.20.0.5",
    "dhcp_range_start": "10.20.0.100",
    "dhcp_range_end": "10.20.0.200",
    "status": "Active",
    "tags": "pci",
}


@pytest.fixture()
def admin(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_ipam_rows():
    """Give every test an empty inventory.

    The database is session-scoped, so without this a subnet left behind by one
    test would overlap the next test's block and fail the overlap check for the
    wrong reason. Only this module's fixtures are cleared; users are shared.
    """
    yield
    with SessionLocal() as db:
        for model in (IPHistory, IPAddress, Network, Device):
            db.query(model).delete()
        db.commit()


# Fields pinned to 10.20.0.0/16 in NETWORK_PAYLOAD. Overriding the CIDR would
# otherwise drag these out of range, so they are dropped unless a test sets them.
CIDR_DEPENDENT = ("gateway", "dns_servers", "subnet_mask", "vlan_range_start",
                  "vlan_range_end", "dhcp_server", "dhcp_range_start", "dhcp_range_end")


def _create_network(client, headers, **overrides):
    payload = {**NETWORK_PAYLOAD, **overrides}
    if "cidr" in overrides:
        for key in CIDR_DEPENDENT:
            if key not in overrides:
                payload[key] = None
    return client.post("/api/networks", headers=headers, json=payload)


def _create_ip(client, headers, **overrides):
    payload = {"ip_address": "10.20.0.50", "subnet_prefix": 16, **overrides}
    return client.post("/api/ip-addresses", headers=headers, json=payload)


# --------------------------------------------------------------------------- #
# Networks
# --------------------------------------------------------------------------- #
def test_create_network_with_ipam_attributes(client, admin):
    response = _create_network(client, admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["gateway"] == "10.20.0.1"
    assert body["dns_servers"] == ["10.20.0.2", "10.20.0.3"]
    assert body["environment"] == "Production"
    assert body["criticality"] == "High"
    assert body["vrf"] == "MGMT"
    assert body["vlan_name"] == "USERS"
    assert body["dhcp_enabled"] is True
    assert body["status"] == "Active"
    assert body["cost_center"] == "CC-1042"


def test_network_address_family_follows_cidr(client, admin):
    response = _create_network(client, admin)
    assert response.json()["address_family"] == "IPv4"

    ipv6 = _create_network(
        client, admin,
        network_name="v6-core", network_range="2001:db8::/32", cidr="2001:db8::/32",
        gateway="2001:db8::1", vlan_range_start="2001:db8::1", vlan_range_end="2001:db8::ff",
        dhcp_range_start="2001:db8::100", dhcp_range_end="2001:db8::1f4",
        dns_servers=["2001:4860:4860::8888"],
    )
    assert ipv6.status_code == 201, ipv6.text
    assert ipv6.json()["address_family"] == "IPv6"


def test_network_rejects_overlapping_cidr(client, admin):
    _create_network(client, admin)
    clash = _create_network(client, admin, network_name="Overlap",
                           network_range="10.20.5.0/24", cidr="10.20.5.0/24")
    assert clash.status_code == 409
    assert "overlaps" in clash.json()["detail"]


def test_network_allows_disjoint_cidr(client, admin):
    _create_network(client, admin)
    disjoint = _create_network(client, admin, network_name="Other",
                              network_range="10.30.0.0/16", cidr="10.30.0.0/16")
    assert disjoint.status_code == 201


def test_network_rejects_gateway_outside_cidr(client, admin):
    response = _create_network(client, admin, gateway="192.168.9.1")
    assert response.status_code == 422
    assert "outside" in response.text


def test_network_rejects_half_specified_dhcp_range(client, admin):
    response = _create_network(client, admin, dhcp_range_end=None)
    assert response.status_code == 422
    assert "start and an end" in response.text


def test_network_rejects_inverted_dhcp_range(client, admin):
    response = _create_network(client, admin, dhcp_range_start="10.20.0.200",
                               dhcp_range_end="10.20.0.100")
    assert response.status_code == 422
    assert "must not be above" in response.text


def test_network_rejects_dhcp_range_outside_cidr(client, admin):
    response = _create_network(client, admin, dhcp_range_end="10.21.0.5")
    assert response.status_code == 422
    assert "outside" in response.text


def test_network_rejects_mixed_family_range(client, admin):
    response = _create_network(client, admin, vlan_range_start="2001:db8::1",
                               vlan_range_end="10.20.0.9")
    assert response.status_code == 422
    assert "mixes IPv4 and IPv6" in response.text


def test_network_filters_unusable_dns_servers(client, admin):
    response = _create_network(client, admin, dns_servers=["10.20.0.2", "not-an-ip",
                                                           "10.20.0.2", "10.20.0.4"])
    assert response.status_code == 201
    # The bad entry is dropped and the duplicate collapsed.
    assert response.json()["dns_servers"] == ["10.20.0.2", "10.20.0.4"]


def test_network_parent_must_contain_child(client, admin):
    parent = _create_network(client, admin).json()
    child = _create_network(client, admin, network_name="Child",
                           network_range="192.168.0.0/16", cidr="192.168.0.0/16",
                           parent_network_id=parent["id"])
    assert child.status_code == 409
    assert "does not contain" in child.json()["detail"]


def test_network_accepts_contained_child(client, admin):
    parent = _create_network(client, admin).json()
    child = _create_network(client, admin, network_name="Child",
                           network_range="10.20.5.0/24", cidr="10.20.5.0/24",
                           parent_network_id=parent["id"])
    assert child.status_code == 201
    assert child.json()["parent_network_id"] == parent["id"]


def test_network_rejects_missing_parent(client, admin):
    response = _create_network(client, admin, parent_network_id=987654)
    assert response.status_code == 409
    assert "does not exist" in response.json()["detail"]


def test_network_rejects_self_as_parent(client, admin):
    network = _create_network(client, admin).json()
    response = client.patch(f"/api/networks/{network['id']}", headers=admin,
                            json={"parent_network_id": network["id"]})
    assert response.status_code == 409
    assert "its own parent" in response.json()["detail"]


def test_network_rejects_circular_parent(client, admin):
    parent = _create_network(client, admin).json()
    child = _create_network(client, admin, network_name="Child",
                           network_range="10.20.5.0/24", cidr="10.20.5.0/24",
                           parent_network_id=parent["id"]).json()
    # Point the supernet at its own descendant.
    response = client.patch(f"/api/networks/{parent['id']}", headers=admin,
                            json={"parent_network_id": child["id"]})
    assert response.status_code == 409
    assert "circular" in response.json()["detail"]


def test_network_update_does_not_clash_with_itself(client, admin):
    network = _create_network(client, admin).json()
    response = client.patch(f"/api/networks/{network['id']}", headers=admin,
                            json={"gateway": "10.20.0.9"})
    assert response.status_code == 200
    assert response.json()["gateway"] == "10.20.0.9"


def test_network_update_into_another_network_is_rejected(client, admin):
    first = _create_network(client, admin).json()
    second = _create_network(client, admin, network_name="Second",
                            network_range="10.30.0.0/16", cidr="10.30.0.0/16").json()
    response = client.patch(f"/api/networks/{second['id']}", headers=admin,
                            json={"cidr": "10.20.9.0/24"})
    assert response.status_code == 409
    assert "overlaps" in response.json()["detail"]
    assert first["cidr"] == "10.20.0.0/16"


def test_networks_can_be_searched_and_filtered(client, admin):
    _create_network(client, admin)
    _create_network(client, admin, network_name="Lab", network_range="10.30.0.0/16",
                    cidr="10.30.0.0/16", vlan_name="LAB", environment="Development",
                    status="Planned")
    found = client.get("/api/networks", headers=admin, params={"q": "USERS"})
    assert [n["network_name"] for n in found.json()] == ["Corporate"]
    by_env = client.get("/api/networks", headers=admin, params={"environment": "Development"})
    assert [n["network_name"] for n in by_env.json()] == ["Lab"]
    by_status = client.get("/api/networks", headers=admin, params={"status": "Active"})
    assert [n["network_name"] for n in by_status.json()] == ["Corporate"]


# --------------------------------------------------------------------------- #
# IP addresses
# --------------------------------------------------------------------------- #
def test_ip_can_be_linked_to_subnet(client, admin):
    subnet = _create_network(client, admin).json()
    response = _create_ip(client, admin, subnet_id=subnet["id"])
    assert response.status_code == 201, response.text
    assert response.json()["subnet_id"] == subnet["id"]


def test_ip_rejects_address_outside_subnet(client, admin):
    subnet = _create_network(client, admin).json()
    response = _create_ip(client, admin, ip_address="10.99.0.5", subnet_id=subnet["id"])
    assert response.status_code == 409
    assert "outside subnet" in response.json()["detail"]


def test_ip_rejects_family_mismatch_against_subnet(client, admin):
    subnet = _create_network(client, admin).json()
    response = _create_ip(client, admin, ip_address="2001:db8::5", subnet_prefix=64,
                          subnet_id=subnet["id"])
    assert response.status_code == 409
    assert "is not IPv4" in response.json()["detail"]


def test_ip_rejects_unknown_subnet(client, admin):
    response = _create_ip(client, admin, subnet_id=987654)
    assert response.status_code == 409
    assert "does not exist" in response.json()["detail"]


def test_ip_subnet_is_detected_when_omitted(client, admin):
    subnet = _create_network(client, admin).json()
    response = _create_ip(client, admin)
    assert response.status_code == 201
    assert response.json()["subnet_id"] == subnet["id"]


def test_ip_subnet_left_null_when_no_match(client, admin):
    _create_network(client, admin)
    response = _create_ip(client, admin, ip_address="172.16.5.5")
    assert response.status_code == 201
    assert response.json()["subnet_id"] is None


def test_ip_detects_most_specific_subnet(client, admin):
    supernet = _create_network(client, admin).json()
    # A /24 cannot overlap the /16, so build a nested block by seeding directly.
    with SessionLocal() as db:
        db.add(Network(network_name="Vlan50", network_range="10.20.0.0/24",
                       cidr="10.20.0.0/24", address_family="IPv4"))
        db.commit()
    response = _create_ip(client, admin, ip_address="10.20.0.77")
    assert response.status_code == 201
    assert response.json()["subnet_id"] != supernet["id"]


def test_only_one_primary_address_per_device(client, admin):
    with SessionLocal() as db:
        device = Device(hostname="srv-01")
        db.add(device)
        db.commit()
        device_id = device.id

    first = _create_ip(client, admin, ip_address="10.20.0.51", device_id=device_id,
                       is_primary=True)
    assert first.status_code == 201

    second = _create_ip(client, admin, ip_address="10.20.0.52", device_id=device_id,
                        is_primary=True)
    assert second.status_code == 409
    assert "already has a primary" in second.json()["detail"]

    third = _create_ip(client, admin, ip_address="10.20.0.53", device_id=device_id)
    assert third.status_code == 201, "a secondary address is fine"


def test_primary_address_can_be_reassigned(client, admin):
    with SessionLocal() as db:
        device = Device(hostname="srv-02")
        db.add(device)
        db.commit()
        device_id = device.id

    first = _create_ip(client, admin, ip_address="10.20.0.61", device_id=device_id,
                       is_primary=True).json()
    # Editing the row that already holds the flag must not trip the rule.
    keep = client.patch(f"/api/ip-addresses/{first['id']}", headers=admin,
                        json={"is_primary": True})
    assert keep.status_code == 200
    # Dropping the flag frees the slot for another address.
    dropped = client.patch(f"/api/ip-addresses/{first['id']}", headers=admin,
                           json={"is_primary": False})
    assert dropped.status_code == 200
    second = _create_ip(client, admin, ip_address="10.20.0.62", device_id=device_id,
                        is_primary=True)
    assert second.status_code == 201


def test_ip_allocation_governance_fields(client, admin):
    response = _create_ip(
        client, admin,
        allocation_method="DHCP Reservation", discovery_source="Network Scan",
        reverse_dns="50.0.20.10.example.com", redundancy_group="FHRP-1",
        shared_with="Cluster node B", status_reason="Held for failover",
        approved_by="Jane Doe", status_changed_at="2026-02-01T10:00:00",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["allocation_method"] == "DHCP Reservation"
    assert body["discovery_source"] == "Network Scan"
    assert body["redundancy_group"] == "FHRP-1"
    assert body["approved_by"] == "Jane Doe"


def test_ip_rejects_unknown_allocation_method(client, admin):
    assert _create_ip(client, admin, allocation_method="Carrier Pigeon").status_code == 422


def test_ip_search_covers_reverse_dns_and_approver(client, admin):
    _create_ip(client, admin, reverse_dns="host50.example.com", approved_by="ops-team")
    for term in ("host50", "ops-team", "10.20.0.50"):
        found = client.get("/api/ip-addresses", headers=admin, params={"search": term})
        assert found.json()["total"] == 1, term


def test_ip_can_be_filtered_by_subnet(client, admin):
    subnet = _create_network(client, admin).json()
    _create_network(client, admin, network_name="Second", network_range="10.30.0.0/16",
                    cidr="10.30.0.0/16", vlan_name="SECOND")
    _create_ip(client, admin, subnet_id=subnet["id"])
    other = _create_ip(client, admin, ip_address="10.30.0.9").json()

    by_subnet = client.get("/api/ip-addresses", headers=admin,
                           params={"subnet_id": subnet["id"]}).json()
    assert by_subnet["total"] == 1
    assert by_subnet["items"][0]["ip_address"] == "10.20.0.50"
    assert by_subnet["items"][0]["subnet_id"] != other["subnet_id"]


def test_ip_can_be_filtered_by_primary_flag(client, admin):
    _create_ip(client, admin, is_primary=True)
    _create_ip(client, admin, ip_address="10.20.0.58")
    found = client.get("/api/ip-addresses", headers=admin, params={"is_primary": True})
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["is_primary"] is True


def test_deleting_a_subnet_keeps_its_addresses(client, admin):
    subnet = _create_network(client, admin).json()
    address = _create_ip(client, admin, subnet_id=subnet["id"]).json()

    assert client.delete(f"/api/networks/{subnet['id']}", headers=admin).status_code == 204

    with SessionLocal() as db:
        row = db.get(IPAddress, address["id"])
        assert row is not None
        # ON DELETE SET NULL: the address survives, only the link is dropped.
        assert row.subnet_id is None


def test_network_child_hierarchy_survives_delete(client, admin):
    parent = _create_network(client, admin).json()
    child = _create_network(client, admin, network_name="Child",
                           network_range="10.20.5.0/24", cidr="10.20.5.0/24",
                           parent_network_id=parent["id"]).json()
    assert client.delete(f"/api/networks/{parent['id']}", headers=admin).status_code == 204
    with SessionLocal() as db:
        assert db.get(Network, child["id"]).parent_network_id is None
        # The orphan is now free to claim the CIDR the parent used to hold.
        assert db.scalars(select(Network.cidr)).all() == ["10.20.5.0/24"]

# --------------------------------------------------------------------------- #
# Web rendering
# --------------------------------------------------------------------------- #
# A Jinja syntax error only surfaces when the template is compiled, which the
# JSON API tests never do. These render the real pages so a broken template
# fails here instead of in the browser.
RENDERABLE_PAGES = [
    "/networks",
    "/networks/add",
    "/ip-addresses",
    "/ip-addresses/add",
    "/devices",
]


@pytest.mark.parametrize("path", RENDERABLE_PAGES)
def test_web_pages_render(client, path):
    login(client, "admin", ADMIN_PASSWORD)
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    assert "TemplateSyntaxError" not in response.text


def test_web_network_list_shows_ipam_attributes(client, admin):
    _create_network(client, admin)
    login(client, "admin", ADMIN_PASSWORD)
    body = client.get("/networks").text
    assert "Corporate" in body
    assert "10.20.0.1" in body          # gateway
    assert "Production" in body          # environment
    assert "High" in body                # criticality
    assert "Network Team" in body        # owner
    assert "MGMT" in body                # vrf
    assert "DHCP" in body                # dhcp_enabled pill


def test_web_network_list_shows_child_and_planned_status(client, admin):
    parent = _create_network(client, admin).json()
    _create_network(client, admin, network_name="Child", network_range="10.20.5.0/24",
                    cidr="10.20.5.0/24", parent_network_id=parent["id"],
                    status="Planned", vlan_name="CHILD")
    login(client, "admin", ADMIN_PASSWORD)
    body = client.get("/networks").text
    assert "Child" in body and "Planned" in body


def test_web_network_form_exposes_every_new_field(client):
    login(client, "admin", ADMIN_PASSWORD)
    body = client.get("/networks/add").text
    for field in ("address_family", "gateway", "dns_servers", "vrf", "domain_name",
                  "dhcp_enabled", "dhcp_range_start", "dhcp_range_end", "vlan_name",
                  "vlan_range_start", "environment", "criticality", "owner",
                  "contact_email", "cost_center", "site_code", "parent_network_id"):
        assert f'name="{field}"' in body, f"form is missing {field}"


def test_web_ip_form_exposes_every_new_field(client):
    login(client, "admin", ADMIN_PASSWORD)
    body = client.get("/ip-addresses/add").text
    for field in ("subnet_id", "is_primary", "allocation_method", "discovery_source",
                  "reverse_dns", "redundancy_group", "shared_with", "status_reason",
                  "approved_by"):
        assert f'name="{field}"' in body, f"form is missing {field}"


def test_web_network_submit_shows_validation_error(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/networks/add", data={
        "_csrf": csrf, "network_name": "Bad", "network_range": "10.90.0.0/16",
        "cidr": "10.90.0.0/16", "gateway": "1.2.3.4", "address_family": "IPv4",
        "criticality": "Medium", "status": "Active",
    })
    assert response.status_code == 200
    assert "outside" in response.text


def test_web_network_submit_reports_overlap_on_the_form(client, admin):
    _create_network(client, admin)
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/networks/add", data={
        "_csrf": csrf, "network_name": "Clash", "network_range": "10.20.9.0/24",
        "cidr": "10.20.9.0/24", "address_family": "IPv4",
        "criticality": "Medium", "status": "Active",
    })
    assert response.status_code == 200
    assert "overlaps" in response.text


def test_web_network_submit_persists_new_attributes(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/networks/add", data={
        "_csrf": csrf, "network_name": "Web-Net", "network_range": "10.70.0.0/16",
        "cidr": "10.70.0.0/16", "gateway": "10.70.0.1",
        "dns_servers": ["10.70.0.2", "10.70.0.3"],
        "address_family": "IPv4", "environment": "Staging", "criticality": "Low",
        "status": "Active", "owner": "WebOps", "vrf": "TEST", "dhcp_enabled": "on",
        "dhcp_range_start": "10.70.0.10", "dhcp_range_end": "10.70.0.20",
    }, follow_redirects=True)
    assert response.status_code == 200
    with SessionLocal() as db:
        saved = db.scalars(select(Network).where(Network.network_name == "Web-Net")).one()
        assert saved.gateway == "10.70.0.1"
        assert saved.dns_servers == ["10.70.0.2", "10.70.0.3"]
        assert saved.dhcp_enabled is True
        assert saved.owner == "WebOps"


def test_web_ip_submit_persists_subnet_and_primary(client, admin):
    subnet = _create_network(client, admin).json()
    csrf = login(client, "admin", ADMIN_PASSWORD)
    client.post("/ip-addresses/add", data={
        "_csrf": csrf, "ip_address": "10.20.0.44", "subnet_prefix": "16",
        "subnet_id": str(subnet["id"]), "status": "Active", "allocation_type": "Static",
        "allocation_method": "Static Reservation", "discovery_source": "Manual",
        "is_primary": "on", "approved_by": "webops",
    }, follow_redirects=True)
    with SessionLocal() as db:
        saved = db.scalars(select(IPAddress).where(
            IPAddress.ip_address == "10.20.0.44")).one()
        assert saved.subnet_id == subnet["id"]
        assert saved.is_primary is True
        assert saved.approved_by == "webops"


def test_web_ip_submit_reports_subnet_mismatch(client, admin):
    subnet = _create_network(client, admin).json()
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/ip-addresses/add", data={
        "_csrf": csrf, "ip_address": "10.99.0.5", "subnet_prefix": "16",
        "subnet_id": str(subnet["id"]), "status": "Available", "allocation_type": "Static",
        "allocation_method": "Manual", "discovery_source": "Manual",
    })
    assert response.status_code == 200
    assert "outside subnet" in response.text
