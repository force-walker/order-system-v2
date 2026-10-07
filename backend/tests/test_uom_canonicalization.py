import pytest
from pydantic import ValidationError

from app.core.uom import normalize_uom
from app.schemas.allocation import AllocationOverrideRequest
from app.schemas.product import ProductCreateRequest
from app.schemas.purchase_result import PurchaseResultCreateRequest


@pytest.mark.parametrize(("raw", "expected"), [
    ("KG", "kg"),
    ("Kg", "kg"),
    ("PC", "piece"),
    ("PIECE", "piece"),
    ("count", "piece"),
    ("CTN", "case"),
    ("Case", "case"),
])
def test_uom_aliases_are_canonical_lowercase_ascii(raw, expected):
    assert normalize_uom(raw) == expected
    assert expected.isascii() and expected.isalpha() and expected == expected.lower()


def test_product_and_transaction_inputs_canonicalize_known_aliases():
    product = ProductCreateRequest(
        name="Canonical",
        order_uom="PC",
        purchase_uom="CASE",
        invoice_uom="Case",
        freight_weight="1",
    )
    assert (product.order_uom, product.purchase_uom, product.invoice_uom) == ("piece", "case", "case")

    allocation = AllocationOverrideRequest(
        final_supplier_id=1,
        final_qty=2,
        final_uom="CTN",
        override_reason_code="test",
    )
    assert allocation.final_uom == "case"

    result = PurchaseResultCreateRequest(
        allocation_id=1,
        purchased_qty=2,
        purchased_uom="KG",
        result_status="filled",
    )
    assert result.purchased_uom == "kg"


def test_unknown_uom_is_rejected_instead_of_guessed():
    with pytest.raises(ValidationError):
        AllocationOverrideRequest(
            final_supplier_id=1,
            final_qty=2,
            final_uom="box",
            override_reason_code="test",
        )
