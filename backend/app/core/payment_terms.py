from calendar import monthrange
from datetime import date, timedelta

from app.models.entities import PaymentTermsType


def _month_end(value: date, months: int = 0) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, monthrange(year, month)[1])


def calculate_due_date(
    issue_date: date,
    payment_terms_type: PaymentTermsType | str | None,
    payment_terms_days: int | None = None,
) -> date | None:
    if payment_terms_type is None:
        return None
    terms = PaymentTermsType(payment_terms_type)
    if terms == PaymentTermsType.days_after_issue:
        return issue_date + timedelta(days=payment_terms_days or 0)
    if terms == PaymentTermsType.end_of_issue_month:
        return _month_end(issue_date)
    if terms == PaymentTermsType.end_of_next_month:
        return _month_end(issue_date, 1)
    if terms == PaymentTermsType.end_of_second_month:
        return _month_end(issue_date, 2)
    if terms == PaymentTermsType.half_month_15_eom:
        if issue_date.day <= 15:
            return _month_end(issue_date)
        next_month = _month_end(issue_date, 1)
        return date(next_month.year, next_month.month, 15)
    raise ValueError(f"unsupported payment terms type: {terms}")
