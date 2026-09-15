"""Tests for OAuth (Google/GitHub) sign-in, with provider HTTP calls faked."""
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from tests.conftest import login

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GITHUB_AUTH = "https://github.com/login/oauth/authorize"


def _start(client, path, expected_auth_url):
    response = client.get(path)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(expected_auth_url)
    params = parse_qs(urlparse(location).query)
    assert params["client_id"] and params["redirect_uri"] and params["state"]
    state = params["state"][0]
    return client.cookies.get(f"oauth_state_{path.rsplit('/', 1)[-1]}"), state


def test_login_page_shows_provider_buttons(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Continue with Google" in response.text
    assert "Continue with GitHub" in response.text


def test_oauth_handoff_redirects_to_providers(client_no_redirect):
    _start(client_no_redirect, "/login/google", GOOGLE_AUTH)
    _start(client_no_redirect, "/login/github", GITHUB_AUTH)


def test_callback_creates_user_and_logs_in(client_no_redirect, monkeypatch):
    client_no_redirect.get("/login/google")
    state = client_no_redirect.cookies.get("oauth_state_google")

    monkeypatch.setattr("app.web.oauth._exchange_code", lambda *a: "fake-token")
    monkeypatch.setattr("app.web.oauth._fetch_email_and_name",
                        lambda *a: ("alice@example.org", "Alice Example"))

    response = client_no_redirect.get(f"/auth/callback/google?code=abc&state={state}")
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert "access_token" in client_no_redirect.cookies
    assert client_no_redirect.cookies.get("oauth_state_google") in (None, "")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "alice@example.org"))
        assert user is not None
        assert user.role == "viewer"
        assert user.hashed_password == "!"

    assert client_no_redirect.get("/dashboard").status_code == 200


def test_callback_matches_existing_user_by_email(client_no_redirect, monkeypatch):
    client_no_redirect.get("/login/github")
    state = client_no_redirect.cookies.get("oauth_state_github")

    monkeypatch.setattr("app.web.oauth._exchange_code", lambda *a: "fake-token")
    monkeypatch.setattr("app.web.oauth._fetch_email_and_name",
                        lambda *a: ("viewer@ipam-test.example", "Test Viewer"))

    response = client_no_redirect.get(f"/auth/callback/github?code=abc&state={state}")
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(User).where(User.email == "viewer@ipam-test.example")
        )
        assert count == 1

    # The promoted session is the existing viewer (read-only) account.
    assert client_no_redirect.get("/ip-addresses").status_code == 200


def test_callback_rejects_bad_state(client_no_redirect, monkeypatch):
    client_no_redirect.get("/login/google")
    monkeypatch.setattr("app.web.oauth._exchange_code", lambda *a: "fake-token")
    monkeypatch.setattr("app.web.oauth._fetch_email_and_name",
                        lambda *a: ("bob@example.org", "Bob"))

    response = client_no_redirect.get("/auth/callback/google?code=abc&state=wrong-state")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "access_token" not in client_no_redirect.cookies


def test_callback_rejects_unverified_email(client_no_redirect, monkeypatch):
    client_no_redirect.get("/login/google")
    state = client_no_redirect.cookies.get("oauth_state_google")

    monkeypatch.setattr("app.web.oauth._exchange_code", lambda *a: "fake-token")
    monkeypatch.setattr("app.web.oauth._fetch_email_and_name",
                        lambda *a: (_ for _ in ()).throw(ValueError("Email is not verified")))

    response = client_no_redirect.get(f"/auth/callback/google?code=abc&state={state}")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "access_token" not in client_no_redirect.cookies


def test_oauth_provisioned_user_cannot_login_locally(client_no_redirect, monkeypatch):
    client_no_redirect.get("/login/google")
    state = client_no_redirect.cookies.get("oauth_state_google")
    monkeypatch.setattr("app.web.oauth._exchange_code", lambda *a: "fake-token")
    monkeypatch.setattr("app.web.oauth._fetch_email_and_name",
                        lambda *a: ("carol@example.org", "Carol"))
    client_no_redirect.get(f"/auth/callback/google?code=abc&state={state}")
    client_no_redirect.cookies.clear()  # simulate a fresh, unauthenticated browser
    client_no_redirect.get("/login")
    csrf = client_no_redirect.cookies.get("ipam_csrf")
    response = client_no_redirect.post(
        "/login",
        data={"username": "carol", "password": "any-password", "_csrf": csrf},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "access_token" not in client_no_redirect.cookies