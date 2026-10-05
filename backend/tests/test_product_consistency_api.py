from decimal import Decimal

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
        "order_uom": "piece",
        "purchase_uom": "piece",
        "invoice_uom": "piece",
        "pricing_basis_default": "uom_count",
        "is_catch_weight": False,
        "weight_capture_required": False,
        "freight_weight": "0.25",
    }
    payload.update(overrides)
    if payload["pricing_basis_default"] == "uom_kg" and "freight_weight" not in overrides:
        payload["freight_weight"] = "1"
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
            purchase_uom="KG",
            invoice_uom="KG",
            pricing_basis_default="uom_kg",
            is_catch_weight=True,
            weight_capture_required=True,
        ),
    )
    assert catch.status_code == 201


def test_create_allows_cross_unit_purchasing_and_enforces_kg_pricing_rules(client):
    mismatch = client.post(
        "/api/v1/products",
        json=_payload(
            purchase_uom="KG",
            invoice_uom="KG",
            pricing_basis_default="uom_kg",
            is_catch_weight=True,
            weight_capture_required=True,
        ),
    )
    assert mismatch.status_code == 201

    missing_catch = client.post(
        "/api/v1/products",
        json=_payload(invoice_uom="KG", pricing_basis_default="uom_kg", weight_capture_required=True),
    )
    assert missing_catch.status_code == 422
    assert "UOM_KG_REQUIRES_CATCH_WEIGHT" in _rules(missing_catch)

    missing_weight = client.post(
        "/api/v1/products",
        json=_payload(invoice_uom="KG", pricing_basis_default="uom_kg", is_catch_weight=True),
    )
    assert missing_weight.status_code == 422
    assert "UOM_KG_REQUIRES_WEIGHT_CAPTURE" in _rules(missing_weight)

    wrong_invoice_uom = client.post(
        "/api/v1/products",
        json=_payload(pricing_basis_default="uom_kg", is_catch_weight=True, weight_capture_required=True),
    )
    assert wrong_invoice_uom.status_code == 422
    assert "UOM_KG_REQUIRES_KG_INVOICE_UOM" in _rules(wrong_invoice_uom)


def test_create_rejects_blank_or_unsupported_uom_and_normalizes_case(client):
    unsupported = client.post(
        "/api/v1/products",
        json=_payload(order_uom="PALLET", purchase_uom="PALLET"),
    )
    assert unsupported.status_code == 422
    assert "PRODUCT_UOM_INVALID" in _rules(unsupported)

    normalized = client.post(
        "/api/v1/products",
        json=_payload(order_uom=" PIECE ", purchase_uom="Case", invoice_uom=" CASE "),
    )
    assert normalized.status_code == 201
    assert normalized.json()["order_uom"] == "piece"
    assert normalized.json()["purchase_uom"] == "case"
    assert normalized.json()["invoice_uom"] == "case"
    assert normalize_product_uom(" KG ") == "kg"

    for unsupported_uom in ("PC", "count"):
        rejected = client.post(
            "/api/v1/products",
            json=_payload(order_uom=unsupported_uom, purchase_uom=unsupported_uom, invoice_uom=unsupported_uom),
        )
        assert rejected.status_code == 422
        assert "PRODUCT_UOM_INVALID" in _rules(rejected)


def test_patch_validates_merged_final_state_and_updates_pricing_basis(client):
    created = client.post("/api/v1/products", json=_payload(name="Patch Target"))
    product_id = created.json()["id"]

    updated_cross_unit = client.patch(
        f"/api/v1/products/{product_id}",
        json={"purchase_uom": "CASE", "invoice_uom": "case", "name": "Cross Unit"},
    )
    assert updated_cross_unit.status_code == 200
    current = client.get(f"/api/v1/products/{product_id}").json()
    assert current["name"] == "Cross Unit"
    assert current["purchase_uom"] == "case"
    assert current["invoice_uom"] == "case"

    updated = client.patch(
        f"/api/v1/products/{product_id}",
        json={
            "pricing_basis_default": "uom_kg",
            "purchase_uom": "KG",
            "invoice_uom": "KG",
            "is_catch_weight": True,
            "weight_capture_required": True,
            "freight_weight": "1",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["pricing_basis_default"] == "uom_kg"


def test_freight_weight_rules_apply_to_create_and_patch(client):
    missing = client.post("/api/v1/products", json=_payload(name="Missing freight", freight_weight=None))
    assert missing.status_code == 422
    assert "UOM_COUNT_REQUIRES_FREIGHT_WEIGHT" in _rules(missing)

    zero = client.post("/api/v1/products", json=_payload(name="Zero freight", freight_weight="0"))
    assert zero.status_code == 422
    assert "UOM_COUNT_REQUIRES_FREIGHT_WEIGHT" in _rules(zero)

    count_ok = client.post("/api/v1/products", json=_payload(name="Count freight", freight_weight="0.25"))
    assert count_ok.status_code == 201

    kg_wrong = client.post(
        "/api/v1/products",
        json=_payload(
            name="KG wrong freight",
            pricing_basis_default="uom_kg",
            purchase_uom="kg",
            invoice_uom="kg",
            is_catch_weight=True,
            weight_capture_required=True,
            freight_weight="0.5",
        ),
    )
    assert kg_wrong.status_code == 422
    assert "UOM_KG_FREIGHT_WEIGHT_MUST_BE_ONE" in _rules(kg_wrong)

    kg_ok = client.post(
        "/api/v1/products",
        json=_payload(
            name="KG correct freight",
            pricing_basis_default="uom_kg",
            purchase_uom="kg",
            invoice_uom="kg",
            is_catch_weight=True,
            weight_capture_required=True,
            freight_weight="1",
        ),
    )
    assert kg_ok.status_code == 201


def test_uom_count_exceptions_remain_warnings_not_errors():
    issues = validate_product_master_consistency(
        order_uom="CASE",
        purchase_uom="case",
        invoice_uom="CASE",
        pricing_basis_default=PricingBasis.uom_count,
        is_catch_weight=True,
        weight_capture_required=False,
        freight_weight=Decimal("0.25"),
    )
    assert not [issue for issue in issues if issue.severity == "ERROR"]
    assert {issue.rule for issue in issues if issue.severity == "WARNING"} == {
        "CATCH_WEIGHT_PRICING_BASIS_REVIEW",
        "CATCH_WEIGHT_CAPTURE_FLAG_REVIEW",
    }


def test_canonical_cross_unit_kg_configuration_is_consistent():
    assert product_master_errors(
        order_uom="piece",
        purchase_uom="kg",
        invoice_uom="kg",
        pricing_basis_default=PricingBasis.uom_kg,
        is_catch_weight=True,
        weight_capture_required=True,
        freight_weight=Decimal("1"),
    ) == ()


@pytest.mark.parametrize(
    ("order_uom", "purchase_uom", "invoice_uom", "basis", "catch", "weight", "expected_rule"),
    [
        ("piece", "piece", "piece", PricingBasis.uom_count, False, False, None),
        ("case", "case", "case", PricingBasis.uom_count, False, False, None),
        ("kg", "kg", "kg", PricingBasis.uom_count, False, False, "UOM_COUNT_ORDER_UOM_MUST_BE_COUNTABLE"),
        ("piece", "case", "case", PricingBasis.uom_count, False, False, None),
        ("piece", "case", "piece", PricingBasis.uom_count, False, False, "PURCHASE_INVOICE_UOM_MUST_MATCH"),
        ("piece", "kg", "kg", PricingBasis.uom_kg, True, True, None),
        ("case", "kg", "kg", PricingBasis.uom_kg, True, True, None),
        ("kg", "kg", "kg", PricingBasis.uom_kg, True, True, None),
        ("piece", "case", "kg", PricingBasis.uom_kg, True, True, "PURCHASE_INVOICE_UOM_MUST_MATCH"),
        ("piece", "kg", "case", PricingBasis.uom_kg, True, True, "UOM_KG_REQUIRES_KG_INVOICE_UOM"),
    ],
)
def test_canonical_uom_rule_matrix(order_uom, purchase_uom, invoice_uom, basis, catch, weight, expected_rule):
    errors = product_master_errors(
        order_uom=order_uom,
        purchase_uom=purchase_uom,
        invoice_uom=invoice_uom,
        pricing_basis_default=basis,
        is_catch_weight=catch,
        weight_capture_required=weight,
        freight_weight=Decimal("1") if basis == PricingBasis.uom_kg else Decimal("0.25"),
    )
    rules = {issue.rule for issue in errors}
    if expected_rule is None:
        assert rules == set()
    else:
        assert expected_rule in rules


def test_bulk_create_update_and_upsert_reject_inconsistent_rows_atomically(client):
    create = client.post(
        "/api/v1/products/bulk/create",
        json={"items": [
            {"sku": "SKU-CONSISTENT-BULK", **_payload(name="Valid")},
            {"sku": "SKU-INCONSISTENT-BULK", **_payload(name="Invalid", pricing_basis_default="uom_kg")},
        ]},
    )
    assert create.status_code == 422
    assert all(row["sku"] != "SKU-CONSISTENT-BULK" for row in client.get("/api/v1/products").json())

    target = client.post("/api/v1/products", json=_payload(name="Bulk Update Target")).json()
    update = client.patch(
        "/api/v1/products/bulk/update",
        json={"items": [{"id": target["id"], "pricing_basis_default": "uom_kg"}]},
    )
    assert update.status_code == 422

    upsert = client.post(
        "/api/v1/products/bulk/upsert",
        json={"items": [{"sku": "SKU-BAD-UPSERT", **_payload(pricing_basis_default="uom_kg")}]},
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
            {"import_key": "CONSISTENCY-TARGET", "pricing_basis_default": "uom_kg"},
        ]},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["created"] == 0
    assert body["updated"] == 0
    assert body["failed"] == 1
    error = next(row for row in body["errors"] if row["rule"] == "UOM_KG_REQUIRES_CATCH_WEIGHT")
    assert error["row"] == 2
    assert error["sku"] == seeded_row["sku"]
    assert error["field"] == "is_catch_weight"
    assert error["rule"] == "UOM_KG_REQUIRES_CATCH_WEIGHT"
    rows = client.get("/api/v1/products?include_inactive=true").json()
    assert all(row.get("import_key") != "CONSISTENCY-VALID" for row in rows)

    valid_cross_unit = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [{
            "import_key": "CONSISTENCY-CROSS-UNIT",
            **_payload(
                name="Cross-unit KG product",
                purchase_uom="KG",
                invoice_uom="KG",
                pricing_basis_default="uom_kg",
                is_catch_weight=True,
                weight_capture_required=True,
            ),
        }]},
    )
    assert valid_cross_unit.status_code == 200
    assert valid_cross_unit.json()["created"] == 1
