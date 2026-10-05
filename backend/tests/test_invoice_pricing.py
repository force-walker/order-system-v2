from decimal import Decimal
from types import SimpleNamespace

from app.core.invoice_pricing import (
    compute_default_sales_unit_price,
    compute_draft_margin,
    compute_invoice_cost_basis,
    compute_unit_freight_cost,
    compute_weighted_purchase_unit_cost,
)


def _settings(**overrides):
    values = {
        "exchange_rate": Decimal("20"),
        "jp_gross_margin_pct": Decimal("10"),
        "hk_gross_margin_pct": Decimal("25"),
        "freight_unit_price": Decimal("40"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_freight_cost_for_count_and_kg_products():
    settings = _settings()
    assert compute_unit_freight_cost(freight_weight=Decimal("0.25"), settings=settings) == Decimal("10.00")
    assert compute_unit_freight_cost(freight_weight=Decimal("1"), settings=settings) == Decimal("40")


def test_invoice_cost_and_sales_default_follow_margin_gross_up_without_early_rounding():
    settings = _settings()
    cost_basis = compute_invoice_cost_basis(
        jpy_purchase_unit_cost=Decimal("1000"),
        freight_weight=Decimal("0.25"),
        settings=settings,
    )
    assert cost_basis == Decimal("1000") / Decimal("20") / Decimal("0.9") + Decimal("10")
    assert compute_default_sales_unit_price(unit_cost_basis=cost_basis, settings=settings) == Decimal("87.41")


def test_weighted_purchase_cost_prefers_the_values_supplied_by_each_result():
    assert compute_weighted_purchase_unit_cost([
        (Decimal("1"), Decimal("1000")),
        (Decimal("3"), Decimal("1200")),
    ]) == Decimal("1150")
    assert compute_weighted_purchase_unit_cost([(Decimal("1"), None)]) is None


def test_gross_profit_and_margin_are_positive_when_sales_exceeds_cost():
    quantity = Decimal("18.2")
    cost_basis = Decimal("65.555555")
    sales_price = Decimal("87.41")
    gross_profit = (sales_price - cost_basis) * quantity
    assert gross_profit > 0
    margin = compute_draft_margin(sales_unit_price=sales_price, unit_cost_basis=cost_basis)
    assert margin.gross_margin_unavailable is False
    assert margin.gross_margin_pct == 25.0
