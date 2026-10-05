"""Tests for the REST API and CSRF-protected web mutations."""
from tests.conftest import ADMIN_PASSWORD, VIEWER_PASSWORD, api_token, login


def test_api_login_and_me(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["role"] == "admin"


def test_api_viewer_cannot_create_user(client):
    token = api_token(client, "viewer", VIEWER_PASSWORD)
    response = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "newbie", "email": "newbie@ipam-test.example", "password": "password-123456", "role": "viewer"},
    )
    assert response.status_code == 403


def test_api_admin_crud_ip(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "192.168.55.10", "subnet_prefix": 24, "hostname": "test-host-01"},
    )
    assert created.status_code == 201
    created_id = created.json()["id"]

    listed = client.get("/api/ip-addresses", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    updated = client.patch(
        f"/api/ip-addresses/{created_id}",
        headers=headers,
        json={"hostname": "test-host-renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["hostname"] == "test-host-renamed"

    deleted = client.delete(f"/api/ip-addresses/{created_id}", headers=headers)
    assert deleted.status_code == 204


def test_api_viewer_read_only(client):
    token = api_token(client, "viewer", VIEWER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "192.168.55.99", "subnet_prefix": 24},
    )
    assert response.status_code == 403

    read = client.get("/api/ip-addresses", headers=headers)
    assert read.status_code == 200


def test_api_rejects_bad_ip(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    response = client.post(
        "/api/ip-addresses",
        headers={"Authorization": f"Bearer {token}"},
        json={"ip_address": "not-an-ip", "subnet_prefix": 24},
    )
    assert response.status_code == 422


def test_web_form_mutation_requires_csrf(client):
    login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/networks/add", data={"network_name": "X", "network_range": "10.0.0.0/24", "cidr": "10.0.0.0/24"})
    assert response.status_code == 400


def test_web_add_and_delete_ip_with_csrf(client):
    login(client, "admin", ADMIN_PASSWORD)
    csrf = client.cookies.get("ipam_csrf")

    added = client.post(
        "/ip-addresses/add",
        data={
            "_csrf": csrf,
            "ip_address": "10.20.30.40",
            "subnet_prefix": 24,
            "hostname": "csrf-host",
            "status": "Available",
            "allocation_type": "Static",
        },
    )
    assert added.status_code == 200
    assert "csrf-host" in added.text

    listed = client.get("/ip-addresses")
    assert listed.status_code == 200
    assert "10.20.30.40" in listed.text


def test_api_stores_multiple_mac_addresses(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={
            "ip_address": "192.168.56.10",
            "subnet_prefix": 24,
            "mac_addresses": ["AA:BB:CC:DD:EE:01", "AA-BB-CC-DD-EE-02", "aa:bb:cc:dd:ee:03"],
        },
    )
    assert created.status_code == 201
    assert created.json()["mac_addresses"] == [
        "AA:BB:CC:DD:EE:01",
        "AA-BB-CC-DD-EE-02",
        "aa:bb:cc:dd:ee:03",
    ]

    fetched = client.get(f"/api/ip-addresses/{created.json()['id']}", headers=headers)
    assert fetched.status_code == 200
    assert len(fetched.json()["mac_addresses"]) == 3

    found = client.get("/api/ip-addresses", headers=headers, params={"search": "AA:BB:CC:DD:EE:01"})
    assert found.status_code == 200
    assert found.json()["total"] == 1

    client.delete(f"/api/ip-addresses/{created.json()['id']}", headers=headers)


def test_api_accepts_separated_string_and_deduplicates(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={
            "ip_address": "192.168.57.10",
            "subnet_prefix": 24,
            "mac_addresses": "AA:BB:CC:DD:EE:10, aa:bb:cc:dd:ee:10;AA:BB:CC:DD:EE:11",
        },
    )
    assert created.status_code == 201
    assert created.json()["mac_addresses"] == ["AA:BB:CC:DD:EE:10", "AA:BB:CC:DD:EE:11"]

    client.delete(f"/api/ip-addresses/{created.json()['id']}", headers=headers)


def test_api_rejects_invalid_and_excess_mac_addresses(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    bad = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={
            "ip_address": "192.168.58.10",
            "subnet_prefix": 24,
            "mac_addresses": ["AA:BB:CC:DD:EE:FF", "not-a-mac"],
        },
    )
    assert bad.status_code == 422

    too_many = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={
            "ip_address": "192.168.59.10",
            "subnet_prefix": 24,
            "mac_addresses": [f"AA:BB:CC:DD:EE:{n:02X}" for n in range(21)],
        },
    )
    assert too_many.status_code == 422


def test_web_form_accepts_repeated_mac_addresses(client):
    login(client, "admin", ADMIN_PASSWORD)
    csrf = client.cookies.get("ipam_csrf")

    added = client.post(
        "/ip-addresses/add",
        data={
            "_csrf": csrf,
            "ip_address": "10.30.40.50",
            "subnet_prefix": "24",
            "status": "Active",
            "allocation_type": "Static",
            "hostname": "multi-mac-host",
            "mac_addresses": ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"],
        },
    )
    assert added.status_code == 200

    edit_form = client.get("/ip-addresses")
    assert edit_form.status_code == 200

    token = api_token(client, "admin", ADMIN_PASSWORD)
    listed = client.get(
        "/api/ip-addresses",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": "10.30.40.50"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["mac_addresses"] == [
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:02",
        "AA:BB:CC:DD:EE:03",
    ]


def test_web_form_renders_saved_mac_addresses_on_edit(client):
    login(client, "admin", ADMIN_PASSWORD)
    csrf = client.cookies.get("ipam_csrf")

    created = client.post(
        "/ip-addresses/add",
        data={
            "_csrf": csrf,
            "ip_address": "10.40.50.60",
            "subnet_prefix": "24",
            "status": "Available",
            "allocation_type": "Static",
            "mac_addresses": ["AA:BB:CC:DD:EE:21", "AA:BB:CC:DD:EE:22"],
        },
    )
    assert created.status_code == 200

    token = api_token(client, "admin", ADMIN_PASSWORD)
    listed = client.get(
        "/api/ip-addresses",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": "10.40.50.60"},
    )
    item_id = listed.json()["items"][0]["id"]

    edit_page = client.get(f"/ip-addresses/{item_id}/edit")
    assert edit_page.status_code == 200
    assert edit_page.text.count('name="mac_addresses"') == 3  # two values + template row
    assert "AA:BB:CC:DD:EE:21" in edit_page.text
    assert "AA:BB:CC:DD:EE:22" in edit_page.text


def _make_device(client, headers, hostname, status="Active"):
    created = client.post(
        "/api/devices",
        headers=headers,
        json={"hostname": hostname, "status": status},
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_api_assigns_ip_addresses_to_device(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    device_id = _make_device(client, headers, "assigned-host-01")

    for index, address in enumerate(["10.60.0.11", "10.60.0.12"]):
        created = client.post(
            "/api/ip-addresses",
            headers=headers,
            json={
                "ip_address": address,
                "subnet_prefix": 24,
                "device_id": device_id,
                "interface_name": f"eth{index}",
                "mac_addresses": f"AA:BB:CC:DD:F0:{index:02X}",
            },
        )
        assert created.status_code == 201
        assert created.json()["device_id"] == device_id

    device = client.get(f"/api/devices/{device_id}", headers=headers).json()
    assert device["ip_addresses"] == ["10.60.0.11", "10.60.0.12"]

    client.delete(f"/api/devices/{device_id}", headers=headers)


def test_api_rejects_unknown_device_assignment(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    response = client.post(
        "/api/ip-addresses",
        headers={"Authorization": f"Bearer {token}"},
        json={"ip_address": "10.60.0.99", "subnet_prefix": 24, "device_id": 987654},
    )
    assert response.status_code == 404


def test_deleting_device_keeps_its_ip_addresses_unassigned(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    device_id = _make_device(client, headers, "doomed-host-01")

    created = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "10.61.0.10", "subnet_prefix": 24, "device_id": device_id},
    )
    assert created.status_code == 201
    ip_id = created.json()["id"]

    assert client.delete(f"/api/devices/{device_id}", headers=headers).status_code == 204

    survivor = client.get(f"/api/ip-addresses/{ip_id}", headers=headers)
    assert survivor.status_code == 200
    assert survivor.json()["device_id"] is None

    client.delete(f"/api/ip-addresses/{ip_id}", headers=headers)


def test_web_form_assigns_device_and_lists_it_on_device_page(client):
    login(client, "admin", ADMIN_PASSWORD)
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    device_id = _make_device(client, headers, "web-assigned-host")

    csrf = client.cookies.get("ipam_csrf")
    added = client.post(
        "/ip-addresses/add",
        data={
            "_csrf": csrf,
            "ip_address": "10.62.0.10",
            "subnet_prefix": "24",
            "status": "Active",
            "device_id": str(device_id),
            "interface_name": "bond0",
        },
    )
    assert added.status_code == 200

    device_page = client.get(f"/devices/{device_id}/edit")
    assert device_page.status_code == 200
    assert "10.62.0.10" in device_page.text
    assert "bond0" in device_page.text

    filtered = client.get(f"/ip-addresses?device_id={device_id}")
    assert filtered.status_code == 200
    assert "10.62.0.10" in filtered.text
    assert "10.62.0.99" not in filtered.text

    ip_id = client.get(
        "/api/ip-addresses", headers=headers, params={"search": "10.62.0.10"}
    ).json()["items"][0]["id"]
    client.delete(f"/api/ip-addresses/{ip_id}", headers=headers)
    client.delete(f"/api/devices/{device_id}", headers=headers)


def test_web_form_rejects_unknown_device(client):
    login(client, "admin", ADMIN_PASSWORD)
    response = client.post(
        "/ip-addresses/add",
        data={
            "_csrf": client.cookies.get("ipam_csrf"),
            "ip_address": "10.63.0.10",
            "subnet_prefix": "24",
            "device_id": "987654",
        },
    )
    assert response.status_code == 200
    assert "Device 987654 does not exist." in response.text


def test_dashboard_and_stats_report_device_status(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    active_id = _make_device(client, headers, "status-host-active", "Active")
    maintenance_id = _make_device(client, headers, "status-host-maint", "Maintenance")

    assigned = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "10.64.0.10", "subnet_prefix": 24, "device_id": active_id},
    )
    assert assigned.status_code == 201
    ip_id = assigned.json()["id"]

    stats = client.get("/api/stats", headers=headers).json()
    assert stats["device_stats"]["active"] >= 1
    assert stats["device_stats"]["maintenance"] >= 1
    assert stats["device_count"] == stats["device_stats"]["total"]
    assert stats["assigned_ip_count"] >= 1
    assert stats["assigned_ip_count"] + stats["unassigned_ip_count"] == stats["ip_stats"]["total"]

    login(client, "admin", ADMIN_PASSWORD)
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Device Status" in dashboard.text
    assert "Assigned IPs" in dashboard.text
    assert "status-host-active" in dashboard.text

    client.delete(f"/api/ip-addresses/{ip_id}", headers=headers)
    client.delete(f"/api/devices/{active_id}", headers=headers)
    client.delete(f"/api/devices/{maintenance_id}", headers=headers)


def test_api_filters_ip_addresses_by_device(client):
    token = api_token(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    device_id = _make_device(client, headers, "filter-host-01")

    assigned = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "10.65.0.10", "subnet_prefix": 24, "device_id": device_id},
    )
    assert assigned.status_code == 201
    unassigned = client.post(
        "/api/ip-addresses",
        headers=headers,
        json={"ip_address": "10.65.0.11", "subnet_prefix": 24},
    )
    assert unassigned.status_code == 201

    listed = client.get("/api/ip-addresses", headers=headers, params={"device_id": device_id})
    assert listed.status_code == 200
    assert [item["ip_address"] for item in listed.json()["items"]] == ["10.65.0.10"]

    assert client.get(
        "/api/ip-addresses", headers=headers, params={"device_id": 0}
    ).status_code == 422

    client.delete(f"/api/ip-addresses/{assigned.json()['id']}", headers=headers)
    client.delete(f"/api/ip-addresses/{unassigned.json()['id']}", headers=headers)
    client.delete(f"/api/devices/{device_id}", headers=headers)
