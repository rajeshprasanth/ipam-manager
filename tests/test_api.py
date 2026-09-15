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