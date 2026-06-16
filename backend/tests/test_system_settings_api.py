import json
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import AuditLog, SystemSettings


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _client() -> TestClient:
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed_settings() -> None:
    db = TestingSessionLocal()
    exists = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if exists is None:
        db.add(
            SystemSettings(
                id=1,
                exchange_rate=Decimal("1.0000"),
                jp_gross_margin_pct=Decimal("25.0"),
                hk_gross_margin_pct=Decimal("20.0"),
                freight_unit_price=Decimal("0.00"),
            )
        )
        db.commit()
    db.close()


def _auth(role: str = "admin") -> dict[str, str]:
    access, _, _ = issue_tokens("settings-user", role)
    return {"Authorization": f"Bearer {access}"}


def test_get_and_put_system_settings_with_audit_log():
    _seed_settings()
    client = _client()

    get_res = client.get("/api/v1/system-settings")
    assert get_res.status_code == 200
    assert Decimal(get_res.json()["exchange_rate"]) == Decimal("1.0000")
    assert Decimal(get_res.json()["jp_gross_margin_pct"]) == Decimal("25.000")

    update_res = client.put(
        "/api/v1/system-settings",
        json={
            "exchange_rate": "7.8125",
            "jp_gross_margin_pct": "26.5",
            "hk_gross_margin_pct": "18.25",
            "freight_unit_price": "12.34",
        },
    )
    assert update_res.status_code == 200
    body = update_res.json()
    assert Decimal(body["exchange_rate"]) == Decimal("7.8125")
    assert Decimal(body["jp_gross_margin_pct"]) == Decimal("26.5")
    assert Decimal(body["jp_gross_margin_rate"]) == Decimal("26.5")
    assert Decimal(body["hk_gross_margin_pct"]) == Decimal("18.25")
    assert Decimal(body["freight_unit_price"]) == Decimal("12.34")

    db = TestingSessionLocal()
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "system_settings", AuditLog.entity_id == 1)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert audit.action == "update"
    assert json.loads(audit.before_json)["exchange_rate"] == 1.0
    assert json.loads(audit.after_json)["exchange_rate"] == 7.8125
    db.close()


def test_system_settings_validation_errors_return_422():
    _seed_settings()
    client = _client()

    res = client.put(
        "/api/v1/system-settings",
        json={
            "exchange_rate": "0",
            "jp_gross_margin_pct": "-1",
            "hk_gross_margin_pct": "0",
            "freight_unit_price": "-0.01",
        },
    )
    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"]["details"], list)


def test_system_settings_accepts_jp_gross_margin_rate_alias():
    _seed_settings()
    client = _client()

    res = client.put(
        "/api/v1/system-settings",
        json={
            "exchange_rate": "1.2500",
            "jp_gross_margin_rate": "22.5",
            "hk_gross_margin_pct": "15.0",
            "freight_unit_price": "3.50",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert Decimal(body["jp_gross_margin_pct"]) == Decimal("22.5")
    assert Decimal(body["jp_gross_margin_rate"]) == Decimal("22.5")


def test_system_settings_audit_timeline_is_queryable():
    _seed_settings()
    client = _client()

    client.put(
        "/api/v1/system-settings",
        json={
            "exchange_rate": "2.5000",
            "jp_gross_margin_pct": "30.0",
            "hk_gross_margin_pct": "15.0",
            "freight_unit_price": "5.00",
        },
    )

    timeline = client.get("/api/v1/audit-logs/entities/system_settings/1", headers=_auth())
    assert timeline.status_code == 200
    assert timeline.json()["total"] >= 1
    assert timeline.json()["items"][0]["action"] == "update"
