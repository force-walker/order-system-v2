from dataclasses import dataclass

from app.models.entities import PricingBasis


# These are distinct supported UOM codes, not semantic aliases.  In particular,
# PC and piece (and CASE and CTN) remain different values for equality checks.
SUPPORTED_PRODUCT_UOMS = frozenset({"box", "case", "count", "ctn", "kg", "pc", "piece"})


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
) -> tuple[ProductConsistencyIssue, ...]:
    """Return hard errors and review warnings for one final Product state.

    A uom_kg Order Item already makes PurchaseResult.actual_weight_kg required
    in both the UI and backend.  Therefore no additional H4 flag combination
    currently makes weight capture impossible.
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

    order_value = normalized["order_uom"]
    purchase_value = normalized["purchase_uom"]
    invoice_value = normalized["invoice_uom"]
    if (
        order_value in SUPPORTED_PRODUCT_UOMS
        and purchase_value in SUPPORTED_PRODUCT_UOMS
        and order_value != purchase_value
    ):
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="purchase_uom",
            rule="ORDER_PURCHASE_UOM_MISMATCH",
            message="Order UOM and Purchase UOM must match until a conversion workflow is configured.",
        ))

    if is_catch_weight and invoice_value in SUPPORTED_PRODUCT_UOMS and invoice_value != "kg":
        issues.append(ProductConsistencyIssue(
            severity="ERROR",
            field="invoice_uom",
            rule="CATCH_WEIGHT_INVOICE_UOM_REQUIRED",
            message="Catch-weight products must use KG as Invoice UOM.",
        ))

    pricing_basis = (
        pricing_basis_default.value
        if isinstance(pricing_basis_default, PricingBasis)
        else str(pricing_basis_default)
    )
    if pricing_basis == PricingBasis.uom_kg.value and invoice_value != "kg":
        issues.append(ProductConsistencyIssue(
            severity="WARNING",
            field="invoice_uom",
            rule="UOM_KG_INVOICE_UOM_REVIEW",
            message="uom_kg pricing normally uses KG as Invoice UOM; review this product.",
        ))
    if pricing_basis == PricingBasis.uom_kg.value and not weight_capture_required:
        issues.append(ProductConsistencyIssue(
            severity="WARNING",
            field="weight_capture_required",
            rule="UOM_KG_WEIGHT_CAPTURE_RECOMMENDED",
            message="uom_kg pricing captures actual weight through the Order Item rule, but the Product flag is disabled.",
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
    if (
        pricing_basis == PricingBasis.uom_count.value
        and purchase_value in SUPPORTED_PRODUCT_UOMS
        and invoice_value in SUPPORTED_PRODUCT_UOMS
        and purchase_value != invoice_value
    ):
        issues.append(ProductConsistencyIssue(
            severity="WARNING",
            field="invoice_uom",
            rule="FIXED_UNIT_INVOICE_UOM_REVIEW",
            message="uom_count product has different Purchase and Invoice UOM values.",
        ))

    return tuple(issues)


def product_master_errors(**values) -> tuple[ProductConsistencyIssue, ...]:
    return tuple(issue for issue in validate_product_master_consistency(**values) if issue.severity == "ERROR")
