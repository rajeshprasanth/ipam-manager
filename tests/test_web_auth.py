"""End-to-end tests for the web portal: authentication and role-based access."""
from tests.conftest import ADMIN_PASSWORD, VIEWER_PASSWORD, login


def test_landing_page_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "IPAM" in response.text
    assert "Launch Portal" in response.text


def test_landing_links_point_to_web_routes_not_api(client):
    """Route-name collisions must not hijack url_for (e.g. web 'login' vs api 'login')."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="http://testserver/login"' in response.text
    assert "/api/auth/login" not in response.text


def test_landing_and_login_show_project_owner_and_copyright(client):
    landing = client.get("/")
    assert landing.status_code == 200
    assert "IPAM Manager" in landing.text
    assert "Acme Networks" in landing.text
    assert "Copyright (c) 2026 Acme Networks" in landing.text

    login = client.get("/login")
    assert login.status_code == 200
    assert "IPAM Manager" in login.text
    assert "Acme Networks" in login.text
    assert "Copyright (c) 2026 Acme Networks" in login.text


def test_unauthenticated_dashboard_redirects(client_no_redirect):
    response = client_no_redirect.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_admin_login_and_dashboard(client):
    login(client, "admin", ADMIN_PASSWORD)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_invalid_login_is_rejected(client_no_redirect):
    client_no_redirect.get("/login")
    csrf = client_no_redirect.cookies.get("ipam_csrf")
    response = client_no_redirect.post(
        "/login",
        data={"username": "admin", "password": "wrong-password", "_csrf": csrf},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_viewer_cannot_open_user_management(client_no_redirect):
    login(client_no_redirect, "viewer", VIEWER_PASSWORD)
    response = client_no_redirect.get("/users")
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


def test_viewer_cannot_reach_admin_pages(client_no_redirect):
    login(client_no_redirect, "viewer", VIEWER_PASSWORD)
    for path in ["/ip-addresses/add", "/networks/add", "/devices/add"]:
        response = client_no_redirect.get(path)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


def test_admin_can_open_user_management(client):
    login(client, "admin", ADMIN_PASSWORD)
    response = client.get("/users")
    assert response.status_code == 200
    assert "Test Viewer" in response.text