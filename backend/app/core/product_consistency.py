from dataclasses import dataclass
from decimal import Decimal

from app.models.entities import PricingBasis


# These are the only canonical Product UOM codes. Legacy values such as PC,
# count, and CTN are deliberately not treated as aliases.
SUPPORTED_PRODUCT_UOMS = frozenset({"case", "kg", "piece"})


@dataclass(frozen=True)
class ProductConsistencyIssue:
    severity: str
    field: str
    rule: str
    message: str

    def as_detail(self) -> dict[str, str]:
        return {
            "field": self.field,
            "rule": self.rule,
            "message": self.message,
        }


def normalize_product_uom(value: str | None) -> str | None:
    normalized = (value or "").strip().casefold()
    return normalized or None


def validate_product_master_consistency(
    *,
    order_uom: str | None,
    purchase_uom: str | None,
    invoice_uom: str | None,
    pricing_basis_default: PricingBasis | str,
    is_catch_weight: bool,
    weight_capture_required: bool,
    freight_weight: Decimal | float | None,
) -> tuple[ProductConsistencyIssue, ...]:
    """Return hard errors and review warnings for one final Product state.

    ``uom_kg`` means that customer billing uses measured KG weight.  Cross-unit
    purchasing is valid and is handled by an explicitly entered purchase
    quantity; it is not a Product master inconsistency.
    """
    normalized = {
        "order_uom": normalize_product_uom(order_uom),
        "purchase_uom": normalize_product_uom(purchase_uom),
        "invoice_uom": normalize_product_uom(invoice_uom),
    }
    issues: list[ProductConsistencyIssue] = []

    for field, value in normalized.items():
        if value is None or value not in SUPPORTED_PRODUCT_UOMS:
            issues.append(ProductConsistencyIssue(
                severity="ERROR",
                field=field,
                rule="PRODUCT_UOM_INVALID",
                message=(
                    f"{field} must be one of: {', '.join(sorted(SUPPORTED_PRODUCT_UOMS))}."
                    if value is not None
                    else f"{field} must not be blank."
                ),
            ))

    purchase_value = normalized["purchase_uom"]
    invoice_value = normalized["invoice_uom"]

    pricing_basis = (
        pricing_basis_default.value
        if isinstance(pricing_basis_default, PricingBasis)
        else str(pricing_basis_default)
    )
    freight_weight_value = Decimal(str(freight_weight)) if freight_weight is not None else None
    if pricing_basis == PricingBasis.uom_count.value and (
        freight_weight_value is None or freight_weight_value <= 0
    ):
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="freight_weight",
            rule="UOM_COUNT_REQUIRES_FREIGHT_WEIGHT",
            message="uom_count pricing requires freight_weight greater than 0 KG per invoice unit.",
        ))
    if pricing_basis == PricingBasis.uom_kg.value and freight_weight_value != Decimal("1"):
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="freight_weight",
            rule="UOM_KG_FREIGHT_WEIGHT_MUST_BE_ONE",
            message="uom_kg pricing requires freight_weight to be exactly 1 KG.",
        ))
    if pricing_basis == PricingBasis.uom_count.value and normalized["order_uom"] == "kg":
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="order_uom",
            rule="UOM_COUNT_ORDER_UOM_MUST_BE_COUNTABLE",
            message="uom_count pricing requires piece or case as Order UOM.",
        ))
    if (
        purchase_value in SUPPORTED_PRODUCT_UOMS
        and invoice_value in SUPPORTED_PRODUCT_UOMS
        and purchase_value != invoice_value
    ):
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="invoice_uom",
            rule="PURCHASE_INVOICE_UOM_MUST_MATCH",
            message="Purchase UOM and Invoice UOM must match.",
        ))
    if pricing_basis == PricingBasis.uom_kg.value and not is_catch_weight:
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="is_catch_weight",
            rule="UOM_KG_REQUIRES_CATCH_WEIGHT",
            message="uom_kg pricing requires Catch Weight to be enabled.",
        ))
    if pricing_basis == PricingBasis.uom_kg.value and not weight_capture_required:
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="weight_capture_required",
            rule="UOM_KG_REQUIRES_WEIGHT_CAPTURE",
            message="uom_kg pricing requires Weight Capture Required to be enabled.",
        ))
    if pricing_basis == PricingBasis.uom_kg.value and invoice_value != "kg":
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="invoice_uom",
            rule="UOM_KG_REQUIRES_KG_INVOICE_UOM",
            message="uom_kg pricing requires KG as Invoice UOM.",
        ))
    if is_catch_weight and pricing_basis != PricingBasis.uom_kg.value:
        issues.append(ProductConsistencyIssue(
            severity="WARNING",
            field="pricing_basis_default",
            rule="CATCH_WEIGHT_PRICING_BASIS_REVIEW",
            message="Catch-weight products normally use uom_kg pricing; review this product.",
        ))
    if is_catch_weight and not weight_capture_required:
        issues.append(ProductConsistencyIssue(
            severity="WARNING",
            field="weight_capture_required",
            rule="CATCH_WEIGHT_CAPTURE_FLAG_REVIEW",
            message="Catch-weight product has weight_capture_required disabled.",
        ))
    return tuple(issues)


def product_master_errors(**values) -> tuple[ProductConsistencyIssue, ...]:
    return tuple(issue for issue in validate_product_master_consistency(**values) if issue.severity == "ERROR")
