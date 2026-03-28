from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _responses(path: str, method: str) -> dict:
    spec = client.get("/openapi.json").json()
    return spec["paths"][path][method]["responses"]


def test_openapi_error_contracts_for_core_apis():
    # products
    assert "409" in _responses("/api/v1/products", "post")
    assert "422" in _responses("/api/v1/products", "post")

    # customers
    assert "409" in _responses("/api/v1/customers", "post")
    assert "422" in _responses("/api/v1/customers", "post")

    # orders
    assert "409" in _responses("/api/v1/orders", "post")
    assert "422" in _responses("/api/v1/orders", "post")
    assert "409" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")
    assert "422" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")

    # invoices
    assert "409" in _responses("/api/v1/invoices", "post")
    assert "422" in _responses("/api/v1/invoices", "post")
    assert "409" in _responses("/api/v1/invoices/{invoice_id}/unlock", "post")
    assert "422" in _responses("/api/v1/invoices/{invoice_id}/unlock", "post")

    # allocations / purchase-results
    assert "422" in _responses("/api/v1/allocations/{allocation_id}/override", "patch")
    assert "422" in _responses("/api/v1/purchase-results", "post")

    # auth
    assert "422" in _responses("/api/v1/auth/login", "post")
    assert "401" in _responses("/api/v1/auth/me", "get")

    spec = client.get("/openapi.json").json()
    assert "ApiErrorResponse" in spec["components"]["schemas"]
