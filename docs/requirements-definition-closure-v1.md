# Requirements Definition Closure v1.0

Date: 2026-03-11
Status: Closed for MVP baseline

## Closure scope
Requirements definition is considered complete for MVP with the following finalized decisions.

## Finalized decisions
1. delivery_date
- Mandatory field in order API.
- Default value: next day from order date.
- Editable at creation; post-confirm change is Admin only.

2. target_price requirement
- Optional by default.
- Mandatory when override reason is `better_price` or `urgent_delivery`.

3. supplier final_unit_cost permission
- Supplier can update `final_unit_cost` for assigned lines only.
- All updates must be audit-logged.
- Buyer/Admin must review before invoice finalization.

## MVP completion criteria alignment
- Status model fixed: `new -> confirmed -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`).
- RBAC roles fixed: Admin / 受注入力者 / 発注者 / 仕入先 / 販売先.
- Exception rules, non-functional requirements, API auth policy, report/API I/O definitions, and UAT checklist are prepared.

## Next phase
Proceed to implementation execution (DB migration delta, API completion, UI, UAT run).
