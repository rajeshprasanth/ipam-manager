"""Tests for the enterprise CMDB fields on devices."""
import re

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Device
from tests.conftest import ADMIN_PASSWORD, api_token, login

CMDB_PAYLOAD = {
    "hostname": "esx-host-01",
    "fqdn": "esx01.corp.example.com",
    "asset_tag": "AT-100234",
    "inventory_id": "INV-88213",
    "instance_id": "i-0abc123",
    "barcode": "BC-5512",
    "device_uuid": "4c4c4544-0052-3510",
    "device_class": "Server",
    "device_subtype": "Blade",
    "manufacturer": "Dell",
    "part_number": "SKU-400-A",
    "chassis_type": "2U Rack",
    "lifecycle_status": "In Service",
    "purchase_date": "2024-01-15",
    "warranty_start": "2024-01-20",
    "warranty_end": "2027-01-19",
    "install_date": "2024-02-01",
    "last_audit_date": "2026-08-01",
    "next_review_date": "2027-02-01",
    "device_model": "PowerEdge R650",
    "serial_number": "SN-9931",
    "operating_system": "ESXi 8.0",
    "os_version": "8.0.3",
    "bios_version": "2.19.0",
    "cpu_model": "Intel Xeon Silver 4310",
    "cpu_count": 16,
    "memory_gb": 128,
    "storage_gb": 4096,
    "power_draw_w": 750,
    "weight_kg": "32.50",
    "datacenter": "DC-East",
    "site_code": "SIT-AMS",
    "address": "1 Example Way",
    "city": "Amsterdam",
    "postal_code": "1011AB",
    "country": "NL",
    "floor": "3",
    "room": "SR2",
    "rack": "A1",
    "rack_position": 12,
    "rack_units": 2,
    "slot_position": "Slot 3",
    "latitude": "52.3702000",
    "longitude": "4.8952000",
    "timezone": "Europe/Amsterdam",
    "department": "IT Ops",
    "team": "Platform",
    "business_unit": "Digital Services",
    "cost_center": "CC-4410",
    "managed_by": "Infrastructure Team",
    "approver": "Priya Nair",
    "purchase_cost": "18999.99",
    "currency": "eur",
    "po_number": "PO-99213",
    "contract_number": "CTR-4417",
    "supplier": "Dell Technologies",
    "primary_ip": "10.20.30.40",
    "management_ip": "10.20.30.41",
    "network_segment": "Core VLAN 10",
    "dns_domain": "corp.example.com",
    "port_count": 24,
    "uplink_speed_mbps": 10000,
    "service_name": "Virtualisation",
    "service_group": "Platform",
    "application": "vSphere",
    "redundancy_group": "RG-VC",
    "cluster_name": "cl-prod",
    "rto_minutes": 60,
    "rpo_minutes": 15,
    "maintenance_window": "Sun 01:00-03:00",
    "support_ticket": "INC-10241",
    "change_reference": "CHG-88213",
    "criticality": "Critical",
    "data_classification": "Confidential",
    "compliance_status": "Compliant",
    "compliance_framework": "ISO 27001",
    "patch_status": "Up to Date",
    "patch_due_date": "2026-11-01",
    "antivirus_status": "Protected",
    "backup_status": "Success",
    "discovery_source": "Agent",
    "monitoring_agent": "zabbix-agent 7.0",
}


def _device(hostname: str) -> Device | None:
    with SessionLocal() as db:
        return db.scalars(select(Device).where(Device.hostname == hostname)).first()


def _errors(response) -> str:
    block = re.search(r"alert-danger.*?</ul>", response.text, re.S)
    return " ".join(re.findall(r"<li>(.*?)</li>", block.group(0))) if block else ""


def _add_via_web(client, csrf, **overrides):
    """Submit the device form. csrf is injected here because every login()
    issues a fresh token and these tests each log in again."""
    form = {**_CMDB_FORM_DEFAULTS, **overrides, "_csrf": csrf}
    return client.post("/devices/add", data=form, follow_redirects=True)


_CMDB_FORM_DEFAULTS = {
    "_csrf": "", "hostname": "cmdb-form-host", "status": "Active",
    "asset_tag": "", "device_class": "Server", "lifecycle_status": "In Service",
    "criticality": "Medium", "currency": "eur", "purchase_cost": "10.00",
    "purchase_date": "2024-01-15", "rack_position": "12", "memory_gb": "64",
    "mac_addresses": ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"],
    "is_virtual": "0", "authorized_use": "1", "monitoring_enabled": "1",
}


def test_web_device_persists_cmdb_fields(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = _add_via_web(client, csrf, hostname="cmdb-web-01", asset_tag="AT-100234",
                          criticality="Critical", purchase_cost="18999.99", currency="eur",
                          compliance_status="Compliant", discovery_source="Agent",
                          memory_gb="128", primary_ip="10.20.30.40", latitude="52.3702000")
    assert response.status_code == 200

    device = _device("cmdb-web-01")
    assert device is not None
    assert device.asset_tag == "AT-100234"
    assert device.device_class == "Server"
    assert device.lifecycle_status == "In Service"
    assert device.criticality == "Critical"
    assert device.currency == "EUR"
    assert float(device.purchase_cost) == 18999.99
    assert str(device.purchase_date) == "2024-01-15"
    assert device.rack_position == 12
    assert device.memory_gb == 128
    assert device.latitude is not None
    assert device.compliance_status == "Compliant"
    assert device.discovery_source == "Agent"


def test_web_device_keeps_every_mac_address(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    _add_via_web(client, csrf, hostname="cmdb-mac-01", asset_tag="AT-MAC-01")
    device = _device("cmdb-mac-01")
    # Both repeatable rows must survive; a collapsed getlist() would keep only one.
    assert device.mac_addresses == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]


def test_web_checkbox_unchecked_persists(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    _add_via_web(client, csrf, hostname="cmdb-bool-01", asset_tag="AT-BOOL-01")
    assert _device("cmdb-bool-01").monitoring_enabled is True

    response = client.post(
        f"/devices/{_device('cmdb-bool-01').id}/edit",
        data={**_CMDB_FORM_DEFAULTS, "_csrf": csrf, "hostname": "cmdb-bool-01",
              "asset_tag": "AT-BOOL-01", "is_virtual": "0", "authorized_use": "0",
              "monitoring_enabled": "0", "mac_addresses": ["AA:BB:CC:DD:EE:01"],
              "_csrf": csrf},
        follow_redirects=True,
    )
    assert response.status_code == 200
    device = _device("cmdb-bool-01")
    assert device.monitoring_enabled is False
    assert device.authorized_use is False


def test_web_duplicate_asset_tag_rejected_case_insensitively(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    _add_via_web(client, csrf, hostname="cmdb-dup-01", asset_tag="AT-DUP-01")
    response = _add_via_web(client, csrf, hostname="cmdb-dup-02", asset_tag="at-dup-01")
    assert "already used" in _errors(response)
    assert _device("cmdb-dup-02") is None


def test_web_rejects_self_and_circular_parents(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    _add_via_web(client, csrf, hostname="cmdb-host", asset_tag="AT-HOST")
    host = _device("cmdb-host")

    _add_via_web(client, csrf, hostname="cmdb-vm", asset_tag="AT-VM",
                 parent_device_id=str(host.id), is_virtual="1")
    vm = _device("cmdb-vm")
    assert vm.parent_device_id == host.id

    own = client.post(
        f"/devices/{host.id}/edit",
        data={**_CMDB_FORM_DEFAULTS, "_csrf": csrf, "hostname": "cmdb-host",
              "asset_tag": "AT-HOST", "parent_device_id": str(host.id), "_csrf": csrf},
        follow_redirects=True,
    )
    assert "own parent" in _errors(own)

    loop = client.post(
        f"/devices/{host.id}/edit",
        data={**_CMDB_FORM_DEFAULTS, "_csrf": csrf, "hostname": "cmdb-host",
              "asset_tag": "AT-HOST", "parent_device_id": str(vm.id), "_csrf": csrf},
        follow_redirects=True,
    )
    assert "circular" in _errors(loop)


def test_web_rejects_unknown_parent(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    response = _add_via_web(client, csrf, hostname="cmdb-orphan",
                            parent_device_id="999999")
    assert "does not exist" in _errors(response)
    assert _device("cmdb-orphan") is None


def test_device_list_search_and_filters(client):
    csrf = login(client, "admin", ADMIN_PASSWORD)
    _add_via_web(client, csrf, hostname="cmdb-find-01", asset_tag="AT-SEARCH-9", serial_number="SN-SEARCH-1")
    _add_via_web(client, csrf, hostname="cmdb-find-02", asset_tag="AT-OTHER-9")

    found = client.get("/devices?q=AT-SEARCH-9")
    assert found.status_code == 200
    assert "cmdb-find-01" in found.text
    assert "cmdb-find-02" not in found.text

    by_serial = client.get("/devices?q=SN-SEARCH-1")
    assert "cmdb-find-01" in by_serial.text


def test_api_device_round_trips_cmdb_fields(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/devices", headers=headers,
                         json={**CMDB_PAYLOAD, "asset_tag": "AT-API-ROUNDTRIP"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["asset_tag"] == "AT-API-ROUNDTRIP"
    assert body["currency"] == "EUR"
    assert body["criticality"] == "Critical"
    assert float(body["purchase_cost"]) == 18999.99
    assert body["rack_position"] == 12
    assert body["compliance_status"] == "Compliant"

    fetched = client.get(f"/api/devices/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["site_code"] == "SIT-AMS"

    client.delete(f"/api/devices/{body['id']}", headers=headers)


def test_api_rejects_duplicate_asset_tag(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/api/devices", headers=headers,
                        json={**CMDB_PAYLOAD, "asset_tag": "AT-API-1"})
    assert first.status_code == 201
    duplicate = client.post("/api/devices", headers=headers,
                           json={**CMDB_PAYLOAD, "asset_tag": "at-api-1"})
    assert duplicate.status_code == 409
    assert "already used" in str(duplicate.json()["detail"])
    client.delete(f"/api/devices/{first.json()['id']}", headers=headers)


def test_api_rejects_unknown_parent_and_bad_values(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    orphan = client.post("/api/devices", headers=headers,
                         json={**CMDB_PAYLOAD, "asset_tag": "AT-API-2", "parent_device_id": 987654})
    assert orphan.status_code == 409
    assert "does not exist" in str(orphan.json()["detail"])

    bad_class = client.post("/api/devices", headers=headers,
                            json={**CMDB_PAYLOAD, "device_class": "Toaster"})
    assert bad_class.status_code == 422

    bad_latitude = client.post("/api/devices", headers=headers,
                               json={**CMDB_PAYLOAD, "latitude": 200})
    assert bad_latitude.status_code == 422


@pytest.mark.parametrize("field,value", [
    ("criticality", "Critical"),
    ("lifecycle_status", "Decommissioned"),
    ("device_class", "Virtual Machine"),
])
def test_api_accepts_controlled_vocabularies(client, field, value):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    tag = f"AT-VOCAB-{field[:4].upper()}"
    created = client.post("/api/devices", headers=headers,
                          json={**CMDB_PAYLOAD, "asset_tag": tag, field: value})
    assert created.status_code == 201, created.text
    assert created.json()[field] == value
    client.delete(f"/api/devices/{created.json()['id']}", headers=headers)