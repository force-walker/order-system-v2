from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_validation_error_payload_has_code_message_details():
    res = client.post("/api/v1/customers", json={})
    assert res.status_code == 422
    body = res.json()
    assert body["detail"]["code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"]["message"], str)
    assert isinstance(body["detail"]["details"], list)


def test_business_error_payload_has_code_message_details_key():
    res = client.get("/api/v1/customers/999999")
    assert res.status_code == 404
    body = res.json()
    assert body["detail"]["code"] == "CUSTOMER_NOT_FOUND"
    assert body["detail"]["message"] == "customer not found"
    assert "details" in body["detail"]


def test_list_endpoints_return_array_not_null():
    mappings = client.get("/api/v1/supplier-product-mappings?supplier_id=999999")
    assert mappings.status_code == 200
    assert isinstance(mappings.json(), list)
