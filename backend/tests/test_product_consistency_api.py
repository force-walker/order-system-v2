import pytest
from fastapi.testclient import TestClient

from app.core.product_consistency import (
    normalize_product_uom,
    product_master_errors,
    validate_product_master_consistency,
)
from app.models.entities import PricingBasis
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _payload(**overrides):
    payload = {
        "name": "Consistent Product",
        "order_uom": "PC",
        "purchase_uom": "PC",
        "invoice_uom": "PC",
        "pricing_basis_default": "uom_count",
        "is_catch_weight": False,
        "weight_capture_required": False,
    }
    payload.update(overrides)
    return payload


def _rules(response) -> set[str]:
    return {row["rule"] for row in response.json()["detail"]["details"]}


def test_create_allows_fixed_unit_and_catch_weight_products(client):
    fixed = client.post("/api/v1/products", json=_payload(name="Fixed"))
    assert fixed.status_code == 201

    catch = client.post(
        "/api/v1/products",
        json=_payload(
            name="Catch",
            invoice_uom="KG",
            pricing_basis_default="uom_kg",
            is_catch_weight=True,
            weight_capture_required=True,
        ),
    )
    assert catch.status_code == 201


def test_create_rejects_order_purchase_mismatch_and_catch_weight_non_kg(client):
    mismatch = client.post(
        "/api/v1/products",
        json=_payload(purchase_uom="KG"),
    )
    assert mismatch.status_code == 422
    assert "ORDER_PURCHASE_UOM_MISMATCH" in _rules(mismatch)

    catch = client.post(
        "/api/v1/products",
        json=_payload(is_catch_weight=True, invoice_uom="CASE"),
    )
    assert catch.status_code == 422
    assert "CATCH_WEIGHT_INVOICE_UOM_REQUIRED" in _rules(catch)


def test_create_rejects_blank_or_unsupported_uom_and_normalizes_case(client):
    unsupported = client.post(
        "/api/v1/products",
        json=_payload(order_uom="PALLET", purchase_uom="PALLET"),
    )
    assert unsupported.status_code == 422
    assert "PRODUCT_UOM_INVALID" in _rules(unsupported)

    normalized = client.post(
        "/api/v1/products",
        json=_payload(order_uom=" pc ", purchase_uom="PC", invoice_uom=" pc "),
    )
    assert normalized.status_code == 201
    assert normalize_product_uom(" KG ") == "kg"


def test_patch_validates_merged_final_state_and_updates_pricing_basis(client):
    created = client.post("/api/v1/products", json=_payload(name="Patch Target"))
    product_id = created.json()["id"]

    rejected = client.patch(
        f"/api/v1/products/{product_id}",
        json={"purchase_uom": "KG", "name": "Must Roll Back"},
    )
    assert rejected.status_code == 422
    current = client.get(f"/api/v1/products/{product_id}").json()
    assert current["name"] == "Patch Target"
    assert current["purchase_uom"] == "PC"

    updated = client.patch(
        f"/api/v1/products/{product_id}",
        json={"pricing_basis_default": "uom_kg", "invoice_uom": "KG"},
    )
    assert updated.status_code == 200
    assert updated.json()["pricing_basis_default"] == "uom_kg"


def test_warnings_do_not_block_product_write():
    issues = validate_product_master_consistency(
        order_uom="CASE",
        purchase_uom="case",
        invoice_uom="CASE",
        pricing_basis_default=PricingBasis.uom_kg,
        is_catch_weight=False,
        weight_capture_required=False,
    )
    assert not [issue for issue in issues if issue.severity == "ERROR"]
    assert {issue.rule for issue in issues if issue.severity == "WARNING"} == {
        "UOM_KG_INVOICE_UOM_REVIEW",
        "UOM_KG_WEIGHT_CAPTURE_RECOMMENDED",
    }


def test_sku_000013_target_configuration_is_consistent():
    assert product_master_errors(
        order_uom="PC",
        purchase_uom="PC",
        invoice_uom="KG",
        pricing_basis_default=PricingBasis.uom_kg,
        is_catch_weight=True,
        weight_capture_required=True,
    ) == ()


def test_bulk_create_update_and_upsert_reject_inconsistent_rows_atomically(client):
    create = client.post(
        "/api/v1/products/bulk/create",
        json={"items": [
            {"sku": "SKU-CONSISTENT-BULK", **_payload(name="Valid")},
            {"sku": "SKU-INCONSISTENT-BULK", **_payload(name="Invalid", purchase_uom="KG")},
        ]},
    )
    assert create.status_code == 422
    assert all(row["sku"] != "SKU-CONSISTENT-BULK" for row in client.get("/api/v1/products").json())

    target = client.post("/api/v1/products", json=_payload(name="Bulk Update Target")).json()
    update = client.patch(
        "/api/v1/products/bulk/update",
        json={"items": [{"id": target["id"], "purchase_uom": "KG"}]},
    )
    assert update.status_code == 422

    upsert = client.post(
        "/api/v1/products/bulk/upsert",
        json={"items": [{"sku": "SKU-BAD-UPSERT", **_payload(purchase_uom="KG")}]},
    )
    assert upsert.status_code == 422


def test_import_prevalidates_all_rows_and_reports_row_sku_and_rule(client):
    seeded = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [{"import_key": "CONSISTENCY-TARGET", **_payload(name="Target")}]},
    )
    assert seeded.json()["created"] == 1
    seeded_row = next(
        row for row in client.get("/api/v1/products?include_inactive=true").json()
        if row.get("import_key") == "CONSISTENCY-TARGET"
    )

    result = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [
            {"import_key": "CONSISTENCY-VALID", **_payload(name="Must Not Persist")},
            {"import_key": "CONSISTENCY-TARGET", "purchase_uom": "KG"},
        ]},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["created"] == 0
    assert body["updated"] == 0
    assert body["failed"] == 1
    error = body["errors"][0]
    assert error["row"] == 2
    assert error["sku"] == seeded_row["sku"]
    assert error["field"] == "purchase_uom"
    assert error["rule"] == "ORDER_PURCHASE_UOM_MISMATCH"
    rows = client.get("/api/v1/products?include_inactive=true").json()
    assert all(row.get("import_key") != "CONSISTENCY-VALID" for row in rows)
