from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import create_session_token

client = TestClient(app)


def test_demo_login_returns_session_and_owned_policies():
    response = client.post("/api/v1/auth/login", json={"user_id": "usr_123", "pin": "1234"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "usr_123"
    assert "POL-1092" in data["policies"]
    assert data["access_token"]


def test_invalid_demo_credentials_are_rejected():
    response = client.post("/api/v1/auth/login", json={"user_id": "usr_123", "pin": "wrong"})
    assert response.status_code == 401


def test_chat_requires_authentication():
    response = client.post("/api/v1/chat", json={"user_id": "usr_123", "message": "hello"})
    assert response.status_code == 401


def test_chat_rejects_user_id_token_mismatch():
    token = create_session_token("usr_123")
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": "usr_456", "message": "hello"},
    )
    assert response.status_code == 403


def test_me_returns_authorized_profile():
    token = create_session_token("usr_123")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["policies"] == ["POL-1092"]
