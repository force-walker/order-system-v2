# Invoice Lock & Concurrency Spec Draft (MVP)

Updated: 2026-03-16
Status: Draft (based on Discord decisions)

## 1. Terminology

### 欠番 (missing sequence number)
採番済みの番号が、後続運用で未使用になること。

例:
- `INV/2026/00012` を採番後、処理失敗/取消で最終的に未使用
- 次に `INV/2026/00013` を採番した場合、`00012` は欠番

MVP方針:
- 欠番は許容する（連番の完全連続性は必須要件にしない）

### 重複 (duplicate number)
同一のinvoice_noが複数invoiceに割り当てられること。

MVP方針:
- 重複は不可
- 重複防止を最優先（DB一意制約 + 採番時リトライ）

---

## 2. Invoice Numbering Policy

- Format: `INV/YYYY/00000`
- Re-numbering: not allowed（再採番なし）
- Gap: allowed（欠番許容）
- Duplicate: not allowed（重複禁止）

### Validation rules
- Prefix is fixed `INV`
- `YYYY` = invoice date year
- Sequence is zero-padded 5 digits

### System controls
- DB unique index on `invoice_no`
- Number assignment in transaction boundary
- On unique conflict, server retries sequence issuance and re-attempts once

---

## 3. Invoice Update Lock Policy

- Lock basis: end of month following `invoice_date`
- Rule:
  - Invoice is editable until `last_day(next_month(invoice_date)) 23:59:59` (system timezone)
  - After that, invoice update is locked

### Permission exception
- Unlock operation: Admin only
- Unlock action must be audit-logged with reason

### Notes
- Payment term may differ by customer and is managed separately.
- This lock policy is an operational control for invoice data modification.

---

## 4. Rounding Policy (MVP Unified)

All amount-related rounding uses `floor`.

Scope:
- line amount
- invoice pretax total
- tax amount
- invoice total
- gross margin-related calculated values

Tax base rule (already fixed):
- `tax_amount = floor(total_amount_pretax × tax_rate)`

---

## 5. Concurrency Control (Optimistic Lock)

## 5.1 Why
Prevent silent overwrite when multiple users edit the same record concurrently.

## 5.2 Mechanism
- Each mutable record has `version` (integer, increment-on-update)
- Client sends expected `version` on update
- Server checks latest `version`
  - match => update success, `version = version + 1`
  - mismatch => reject with `409 Conflict`

## 5.3 Target resources
- orders
- order_lines
- supplier_allocations
- invoices
- invoice_lines

## 5.4 API error contract (recommended)

HTTP status: `409 Conflict`

```json
{
  "error_code": "VERSION_CONFLICT",
  "message": "Record has been updated by another user. Please reload and retry.",
  "resource": "invoice",
  "resource_id": "inv_123",
  "current_version": 18
}
```

---

## 6. UI Reload Flow on Conflict (fixed)

1. User presses Save
2. API returns `409 VERSION_CONFLICT`
3. UI shows blocking notice: "他ユーザー更新あり。最新を再読込してください"
4. User clicks Reload button
5. UI fetches latest record
6. User re-edits and re-saves

Optional (future): diff viewer between local edit and latest server state.

---

## 7. All-or-Nothing Transaction Boundaries (fixed)

MVP default policy: transaction unit is invoice/order level for critical batch actions.

- Invoice Finalize: invoice unit all-or-nothing
- Reset to Draft: invoice unit all-or-nothing
- Procurement List Regeneration: order unit all-or-nothing

Failure rule:
- If any hard-stop validation fails, no partial state change is committed.
- State remains unchanged.
- Audit log records failure reason.

---

## 8. Finalized operational decisions (2026-03-17)

1. Unlock scope and permission
- Unlock target: locked invoice with `invoice.status=finalized` only
- Actor: Admin only

2. Unlock TTL
- Unlimited (no auto-expiry)

3. Unlock reason input
- Reason code is mandatory
- Note is optional (<= 500 chars)
- Adopted reason codes:
  - `pricing_correction`
  - `quantity_correction`
  - `tax_correction`
  - `customer_request`
  - `data_fix`
  - `other`

4. Post-unlock edit scope (MVP)
- Admin can edit all invoice fields after unlock

5. Re-lock policy
- No automatic re-lock
- Re-finalize operation is used to re-freeze invoice state

6. Unlock hard-stop conditions
- draft invoice cannot be unlocked
- non-finalized invoice cannot be unlocked
- version conflict blocks unlock

7. Unlock error mapping
- `403 PERMISSION_DENIED`
- `404 INVOICE_NOT_FOUND`
- `409 VERSION_CONFLICT`
- `409 STATUS_TRANSITION_CONFLICT`
- `422 UNLOCK_REASON_REQUIRED`
- `400 INVALID_REASON_CODE`

8. Audit log export in MVP UI
- CSV export only (no advanced UI analytics in MVP)
- Required CSV columns:
  - `event_time`
  - `event_type`
  - `resource_type`
  - `resource_id`
  - `actor`
  - `reason_code`
  - `reason_note`
  - `before_json`
  - `after_json`

---

## 9. Additional validation rules

- Unlock endpoint requires `reason_code`; request without code is `400 INVALID_REASON_CODE`.
- Unlock note is optional but must be <= 500 chars when provided.
- Unlock event and subsequent update events must be linked by `resource_id` in audit logs.
- CSV audit export must include all required columns even when values are null.

## 10. Acceptance Criteria (for UAT linkage)

- Duplicate invoice_no cannot be created under concurrent requests
- Gap in sequence is acceptable and does not block operations
- Invoice edit is blocked after lock date unless Admin unlocks
- Concurrent stale update returns `409 VERSION_CONFLICT`
- UI can recover by reload flow and re-save
- Batch operations above commit all-or-nothing only
