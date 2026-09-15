"""Pytest fixtures: in-memory SQLite database and an app test client."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")
os.environ.setdefault("APP_NAME", "IPAM Manager")
os.environ.setdefault("APP_OWNER", "Acme Networks")
os.environ.setdefault("COPYRIGHT", "Copyright (c) 2026 Acme Networks")
os.environ.setdefault("GOOGLE_CLIENT_ID", "google-test-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "google-test-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "github-test-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "github-test-secret")
os.environ.setdefault("OAUTH_BASE_URL", "http://testserver")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import get_password_hash  # noqa: E402

ADMIN_PASSWORD = "Admin-Pass-123456"
VIEWER_PASSWORD = "Viewer-Pass-123456"


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add_all([
            User(username="admin", email="admin@ipam-test.example", full_name="Test Admin",
                 hashed_password=get_password_hash(ADMIN_PASSWORD), role="admin", is_active=True),
            User(username="viewer", email="viewer@ipam-test.example", full_name="Test Viewer",
                 hashed_password=get_password_hash(VIEWER_PASSWORD), role="viewer", is_active=True),
        ])
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_no_redirect():
    with TestClient(app, follow_redirects=False) as c:
        yield c


def login(client: TestClient, username: str, password: str):
    """Log in through the web form and return the CSRF token used."""
    client.get("/login")
    csrf = client.cookies.get("ipam_csrf")
    client.post(
        "/login",
        data={"username": username, "password": password, "_csrf": csrf},
    )
    return csrf


def api_token(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]