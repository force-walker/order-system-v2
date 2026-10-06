# Invoice history and payment terms

Customer and Supplier payment terms use one of `days_after_issue`, `end_of_issue_month`,
`end_of_next_month`, `end_of_second_month`, or `half_month_15_eom`. Only
`days_after_issue` uses `payment_terms_days`. `half_month_15_eom` means that an issue date
on days 1–15 is due at that month end, while days 16–month-end are due on the 15th of the
following month. All due dates are calculated by `app.core.payment_terms.calculate_due_date`.

An Invoice snapshots its due date when its Draft is generated. Later Customer-master edits
do not rewrite existing invoices. `payment_status` (`unpaid`, `partially_paid`, `paid`) is
independent of the document lifecycle status. Overdue is derived at read time when an unpaid
or partially-paid invoice has `due_date` before today.

`GET /api/v1/invoices/history` performs search, filtering, sorting, and pagination in the
backend. Search covers invoice numbers, Customer name/code, SKU, and Product name without
duplicating Invoice Headers. Header and line CSV exports reuse the same filters and include a
UTF-8 BOM for Japanese Excel compatibility.
