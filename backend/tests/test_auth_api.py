from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.auth import token_hash, utcnow
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.auth import AuthSession, User
from app.models.entities import Customer

PASSWORD = "correct-horse-battery"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    previous = app.dependency_overrides.copy()
    def db_override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    engine.dispose()


def register(client, user_id="alice"):
    return client.post("/api/v1/auth/register", json={"user_id": user_id, "password": PASSWORD})


def login(client, user_id="alice", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"user_id": user_id, "password": password})


def headers(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


def test_registration_login_and_existing_customer_unchanged(auth_client):
    client, engine = auth_client
    with Session(engine) as db:
        db.add(Customer(customer_code="existing", name="Existing customer"))
        db.commit()
    response = register(client)
    assert response.status_code == 201
    assert response.json() == {"user_id": "alice", "role": "order_entry"}
    with Session(engine) as db:
        user = db.get(User, "alice")
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert len(db.scalars(select(Customer)).all()) == 1
        assert db.scalar(select(Customer)).name == "Existing customer"
    tokens = login(client, "ALICE").json()
    assert tokens["token_type"] == "bearer"
    assert client.get("/api/v1/auth/me", headers=headers(tokens)).json() == response.json()
    assert client.get("/api/v1/products", headers=headers(tokens)).status_code == 200
    with Session(engine) as db:
        session = db.scalar(select(AuthSession))
        assert session.access_hash == token_hash(tokens["access_token"])
        assert session.refresh_hash != tokens["refresh_token"]


@pytest.mark.parametrize("user_id,password", [("alice", "wrong"), ("unknown", PASSWORD)])
def test_invalid_credentials(auth_client, user_id, password):
    client, _ = auth_client
    register(client)
    response = login(client, user_id, password)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_duplicate_registration_and_validation(auth_client):
    client, _ = auth_client
    assert register(client).status_code == 201
    assert register(client, "ALICE").status_code == 409
    assert register(client, "spaces not allowed").status_code == 422
    assert client.post("/api/v1/auth/register", json={"user_id": "bob", "password": "short"}).status_code == 422


@pytest.mark.parametrize("extra", [{"role": "admin"}, {"customer_id": 1}, {"email_verified": True}])
def test_registration_cannot_assign_privileges(auth_client, extra):
    client, _ = auth_client
    response = client.post("/api/v1/auth/register", json={"user_id": "alice", "password": PASSWORD, **extra})
    assert response.status_code == 422


def test_old_role_login_and_query_bypass_rejected(auth_client):
    client, _ = auth_client
    assert client.post("/api/v1/auth/login", json={"user_id": "alice", "role": "admin"}).status_code == 422
    assert client.get("/api/v1/products?role=admin&user_id=alice&authenticated=true").status_code == 401
    assert client.get("/api/v1/products", headers={"Authorization": "Bearer fabricated"}).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/products", "/api/v1/customers", "/api/v1/orders", "/api/v1/deliveries",
    "/api/v1/invoices", "/api/v1/suppliers", "/api/v1/system-settings", "/api/v1/auth/me"])
def test_anonymous_api_rejected(auth_client, path):
    client, _ = auth_client
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("use_refresh", [True, False])
def test_logout_revokes_access_and_refresh(auth_client, use_refresh):
    client, _ = auth_client
    register(client)
    tokens = login(client).json()
    other_session = login(client).json()
    kwargs = {"json": {"refresh_token": tokens["refresh_token"]}} if use_refresh else {"headers": headers(tokens)}
    assert client.post("/api/v1/auth/logout", **kwargs).status_code == 200
    assert client.get("/api/v1/products", headers=headers(tokens)).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(other_session)).status_code == 200


def test_refresh_rotation_and_token_types(auth_client):
    client, _ = auth_client
    register(client)
    old = login(client).json()
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + old["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old["access_token"]}).status_code == 401
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(old)).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(response.json())).status_code == 200


def test_expired_session_and_disabled_user(auth_client):
    client, engine = auth_client
    register(client)
    tokens = login(client).json()
    with Session(engine) as db:
        session = db.scalar(select(AuthSession))
        session.access_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me", headers=headers(tokens)).status_code == 401
    with Session(engine) as db:
        db.get(User, "alice").active = False
        db.commit()
    assert login(client).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_email_verification_gate_is_not_bypassed(auth_client, monkeypatch):
    client, _ = auth_client
    register(client)
    tokens = login(client).json()
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    assert register(client, "bob").status_code == 503
    assert login(client).status_code == 403
    assert client.get("/api/v1/auth/me", headers=headers(tokens)).status_code == 403


def test_ordinary_user_cannot_access_admin_metrics(auth_client):
    client, _ = auth_client
    register(client)
    tokens = login(client).json()
    assert client.get("/api/v1/ops/metrics/summary", headers=headers(tokens)).status_code == 403
