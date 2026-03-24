from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_login_refresh_me_flow():
    login = client.post("/api/v1/auth/login", json={"user_id": "u1", "role": "admin"})
    assert login.status_code == 200
    body = login.json()
    assert "access_token" in body
    assert "refresh_token" in body

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == "u1"
    assert me.json()["role"] == "admin"

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_login_forbidden_role():
    res = client.post("/api/v1/auth/login", json={"user_id": "u1", "role": "invalid_role"})
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "FORBIDDEN"
