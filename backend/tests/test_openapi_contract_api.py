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

    # suppliers
    assert "409" in _responses("/api/v1/suppliers", "post")
    assert "422" in _responses("/api/v1/suppliers", "post")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "get")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}", "patch")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "patch")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}", "delete")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "delete")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products", "get")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "409" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products/{product_id}", "delete")

    # orders
    assert "409" in _responses("/api/v1/orders", "post")
    assert "422" in _responses("/api/v1/orders", "post")
    assert "409" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")
    assert "422" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")

    # invoices
    assert "409" in _responses("/api/v1/invoices", "post")
    assert "422" in _responses("/api/v1/invoices", "post")
    assert "409" in _responses("/api/v1/invoices/generate", "post")
    assert "422" in _responses("/api/v1/invoices/generate", "post")
    assert "404" in _responses("/api/v1/invoices/{invoice_id}", "get")
    assert "404" in _responses("/api/v1/invoices/{invoice_id}/items", "get")
    assert "409" in _responses("/api/v1/invoices/{invoice_id}/finalize", "post")
    assert "422" in _responses("/api/v1/invoices/{invoice_id}/finalize", "post")
    assert "409" in _responses("/api/v1/invoices/{invoice_id}/unlock", "post")
    assert "422" in _responses("/api/v1/invoices/{invoice_id}/unlock", "post")

    # allocations / purchase-results
    assert "422" in _responses("/api/v1/allocations/{allocation_id}/override", "patch")
    assert "422" in _responses("/api/v1/purchase-results", "post")
    assert "404" in _responses("/api/v1/purchase-results/{result_id}", "get")

    # auth
    assert "422" in _responses("/api/v1/auth/login", "post")
    assert "401" in _responses("/api/v1/auth/me", "get")

    spec = client.get("/openapi.json").json()
    assert "ApiErrorResponse" in spec["components"]["schemas"]


def test_openapi_phase2_query_filters_are_exposed():
    spec = client.get("/openapi.json").json()

    invoice_list_params = {p["name"] for p in spec["paths"]["/api/v1/invoices"]["get"]["parameters"]}
    assert {"order_id", "status"}.issubset(invoice_list_params)

    purchase_list_params = {p["name"] for p in spec["paths"]["/api/v1/purchase-results"]["get"]["parameters"]}
    assert {"allocation_id", "supplier_id", "limit", "offset"}.issubset(purchase_list_params)

    supplier_list_params = {p["name"] for p in spec["paths"]["/api/v1/suppliers"]["get"]["parameters"]}
    assert {"q", "active", "limit", "offset"}.issubset(supplier_list_params)
