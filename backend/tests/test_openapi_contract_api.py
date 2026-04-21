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
    assert "422" in _responses("/api/v1/products/import-upsert", "post")
    assert "404" in _responses("/api/v1/products/{product_id}/archive", "post")
    assert "404" in _responses("/api/v1/products/{product_id}/unarchive", "post")
    assert "404" in _responses("/api/v1/products/{product_id}", "delete")
    assert "409" in _responses("/api/v1/products/{product_id}", "delete")
    assert "422" in _responses("/api/v1/products/{product_id}", "delete")

    # customers
    assert "409" in _responses("/api/v1/customers", "post")
    assert "422" in _responses("/api/v1/customers", "post")
    assert "404" in _responses("/api/v1/customers/{customer_id}/archive", "post")
    assert "404" in _responses("/api/v1/customers/{customer_id}/unarchive", "post")
    assert "404" in _responses("/api/v1/customers/{customer_id}", "delete")
    assert "409" in _responses("/api/v1/customers/{customer_id}", "delete")
    assert "422" in _responses("/api/v1/customers/{customer_id}", "delete")

    # suppliers
    assert "409" in _responses("/api/v1/suppliers", "post")
    assert "422" in _responses("/api/v1/suppliers", "post")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "get")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}", "patch")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "patch")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/archive", "post")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/unarchive", "post")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}", "delete")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}", "delete")
    assert "409" in _responses("/api/v1/suppliers/{supplier_id}", "delete")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products", "get")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "409" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}/products", "post")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products/{product_id}", "patch")
    assert "422" in _responses("/api/v1/suppliers/{supplier_id}/products/{product_id}", "patch")
    assert "404" in _responses("/api/v1/suppliers/{supplier_id}/products/{product_id}", "delete")

    # supplier-product-mappings (flat)
    assert "404" in _responses("/api/v1/supplier-product-mappings", "post")
    assert "409" in _responses("/api/v1/supplier-product-mappings", "post")
    assert "422" in _responses("/api/v1/supplier-product-mappings", "post")
    assert "404" in _responses("/api/v1/supplier-product-mappings/products/{product_id}", "get")
    assert "404" in _responses("/api/v1/supplier-product-mappings/{mapping_id}", "patch")
    assert "422" in _responses("/api/v1/supplier-product-mappings/{mapping_id}", "patch")
    assert "404" in _responses("/api/v1/supplier-product-mappings/{mapping_id}", "delete")

    # orders
    assert "409" in _responses("/api/v1/orders", "post")
    assert "422" in _responses("/api/v1/orders", "post")
    assert "409" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")
    assert "422" in _responses("/api/v1/orders/{order_id}/bulk-transition", "post")
    assert "409" in _responses("/api/v1/orders/bulk-cancel", "post")
    assert "422" in _responses("/api/v1/orders/bulk-cancel", "post")

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

    # allocations / purchase-results / order-item-allocation-flow
    assert "422" in _responses("/api/v1/allocations/{allocation_id}/override", "patch")
    assert "422" in _responses("/api/v1/purchase-results", "post")
    assert "404" in _responses("/api/v1/purchase-results/{result_id}", "get")
    assert "422" in _responses("/api/v1/order-item-allocations/suggestions", "post")
    assert "404" in _responses("/api/v1/order-item-allocations/suggestions", "post")
    assert "422" in _responses("/api/v1/order-item-allocations/bulk-save", "post")
    assert "409" in _responses("/api/v1/order-item-allocations/bulk-save", "post")

    # reports
    assert "422" in _responses("/api/v1/reports/shipping", "get")

    # auth
    assert "422" in _responses("/api/v1/auth/login", "post")
    assert "401" in _responses("/api/v1/auth/me", "get")

    spec = client.get("/openapi.json").json()
    assert "ApiErrorResponse" in spec["components"]["schemas"]
    assert "details" in spec["components"]["schemas"]["ApiErrorDetail"]["properties"]

    import_error_props = spec["components"]["schemas"]["ProductImportError"]["properties"]
    assert {"index", "import_key", "action", "code", "message", "product_id"}.issubset(import_error_props)

    purchase_result_props = spec["components"]["schemas"]["PurchaseResultResponse"]["properties"]
    assert {"supplier_id", "supplier_name", "invoice_qty", "invoice_uom", "received_qty", "order_uom"}.issubset(purchase_result_props)


def test_openapi_phase2_query_filters_are_exposed():
    spec = client.get("/openapi.json").json()

    invoice_list_params = {p["name"] for p in spec["paths"]["/api/v1/invoices"]["get"]["parameters"]}
    assert {"order_id", "status"}.issubset(invoice_list_params)

    purchase_list_params = {p["name"] for p in spec["paths"]["/api/v1/purchase-results"]["get"]["parameters"]}
    assert {"allocation_id", "customer_id", "product_id", "supplier_id", "sort_by", "sort_order", "limit", "offset"}.issubset(purchase_list_params)

    supplier_list_params = {p["name"] for p in spec["paths"]["/api/v1/suppliers"]["get"]["parameters"]}
    assert {"q", "include_inactive", "active", "limit", "offset"}.issubset(supplier_list_params)

    product_list_params = {p["name"] for p in spec["paths"]["/api/v1/products"]["get"]["parameters"]}
    assert {"include_inactive"}.issubset(product_list_params)

    customer_list_params = {p["name"] for p in spec["paths"]["/api/v1/customers"]["get"]["parameters"]}
    assert {"include_inactive"}.issubset(customer_list_params)

    order_list_params = {p["name"] for p in spec["paths"]["/api/v1/orders"]["get"].get("parameters", [])}
    assert {"stale_delivery_only"}.issubset(order_list_params)

    mapping_list_params = {p["name"] for p in spec["paths"]["/api/v1/supplier-product-mappings"]["get"]["parameters"]}
    assert {"supplier_id", "product_id"}.issubset(mapping_list_params)

    worklist_params = {p["name"] for p in spec["paths"]["/api/v1/order-item-allocations"]["get"]["parameters"]}
    assert {"unallocated_only", "delivery_date", "supplier_id", "product_name", "customer_name", "limit", "offset"}.issubset(worklist_params)

    shipping_report_params = {p["name"] for p in spec["paths"]["/api/v1/reports/shipping"]["get"]["parameters"]}
    assert {"shipped_date", "mode"}.issubset(shipping_report_params)

    bulk_item_schema = spec["components"]["schemas"]["BulkAllocationSaveItem"]
    required_fields = set(bulk_item_schema.get("required", []))
    assert "order_item_id" in required_fields
    assert "supplier_id" not in required_fields
    assert "allocated_qty" not in required_fields

    work_item_schema = spec["components"]["schemas"]["OrderItemAllocationWorkItem"]["properties"]
    assert {"allocated_supplier_id", "allocated_qty", "delivery_date"}.issubset(work_item_schema)

    order_create_props = spec["components"]["schemas"]["OrderCreateRequest"]["properties"]
    assert "delivery_date" in order_create_props
    assert "shipped_date" in order_create_props
    order_create_required = set(spec["components"]["schemas"]["OrderCreateRequest"].get("required", []))
    assert "delivery_date" not in order_create_required

    order_response_props = spec["components"]["schemas"]["OrderResponse"]["properties"]
    assert "shipped_date" in order_response_props

    product_response_props = spec["components"]["schemas"]["ProductResponse"]["properties"]
    assert "legacy_code" in product_response_props
    assert "legacy_unit_code" in product_response_props
    assert "category_code" in product_response_props
    assert "sales_price_6" in product_response_props
    assert "application_category_code" in product_response_props

    cancel_reason_schema = spec["components"]["schemas"].get("OrderCancelReasonCode")
    assert cancel_reason_schema is not None
    assert "stale_delivery" in cancel_reason_schema.get("enum", [])
