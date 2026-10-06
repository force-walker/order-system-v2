from datetime import date, datetime, timezone

import pytest

from app.core.payment_terms import calculate_due_date
from app.core.business_time import hong_kong_today
from app.models.entities import PaymentTermsType
from app.schemas.customer import CustomerCreateRequest
from app.schemas.supplier import SupplierCreateRequest


@pytest.mark.parametrize(("issue", "expected"), [
    (date(2026, 1, 1), date(2026, 1, 31)),
    (date(2026, 1, 15), date(2026, 1, 31)),
    (date(2026, 1, 16), date(2026, 2, 15)),
    (date(2026, 1, 31), date(2026, 2, 15)),
    (date(2026, 2, 15), date(2026, 2, 28)),
    (date(2028, 2, 15), date(2028, 2, 29)),
    (date(2026, 12, 16), date(2027, 1, 15)),
])
def test_half_month_15_eom_boundaries(issue, expected):
    assert calculate_due_date(issue, PaymentTermsType.half_month_15_eom) == expected


def test_all_payment_term_calculations():
    issue = date(2026, 10, 6)
    assert calculate_due_date(issue, PaymentTermsType.days_after_issue, 30) == date(2026, 11, 5)
    assert calculate_due_date(issue, PaymentTermsType.end_of_issue_month) == date(2026, 10, 31)
    assert calculate_due_date(issue, PaymentTermsType.end_of_next_month) == date(2026, 11, 30)
    assert calculate_due_date(issue, PaymentTermsType.end_of_second_month) == date(2026, 12, 31)


def test_half_month_terms_ignore_days_for_customer_and_supplier():
    customer = CustomerCreateRequest(name="C", payment_terms_type="half_month_15_eom", payment_terms_days=99)
    supplier = SupplierCreateRequest(name="S", payment_terms_type="half_month_15_eom", payment_terms_days=99)
    assert customer.payment_terms_days is None
    assert supplier.payment_terms_days is None


def test_days_after_issue_requires_non_negative_days():
    with pytest.raises(ValueError):
        CustomerCreateRequest(name="C", payment_terms_type="days_after_issue")
    with pytest.raises(ValueError):
        SupplierCreateRequest(name="S", payment_terms_type="days_after_issue", payment_terms_days=-1)


def test_hong_kong_today_uses_hong_kong_boundary():
    assert hong_kong_today(datetime(2026, 10, 5, 16, 30, tzinfo=timezone.utc)) == date(2026, 10, 6)
    assert hong_kong_today(datetime(2026, 10, 5, 15, 59, tzinfo=timezone.utc)) == date(2026, 10, 5)
