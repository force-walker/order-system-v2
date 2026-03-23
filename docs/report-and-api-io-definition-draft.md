# 帳票 / API I/O 定義 Draft (MVP)

Updated: 2026-03-15

## 目的
- 画面・CSV・PDF・APIで使う項目名を統一
- 必須/任意、型、フォーマット、コード値を固定
- 実装とUATの判定基準にする

## Source of Truth
- I/O定義の正は `docs/IO_from_order_to_invoice_revised_v_2.xlsx` とする。
- 本書は上記Excelに追従する要約仕様。
- 差分が出た場合はExcelを優先し、本書を更新する。

---

## 1) 共通ルール

- 数量/重量/金額は `numeric/decimal`（float禁止）
- 日付: `YYYY-MM-DD`
- 日時: ISO8601 (`YYYY-MM-DDTHH:mm:ssZ`)
- 仕入通貨: `JPY`
- 販売/請求通貨: `HKD`
- 真偽: `true/false`

コード値（MVP）:
- `order_uom_type`: `uom_count | uom_kg`
- `stockout_policy`: `backorder | substitute | cancel | split`
- `order_status`: `new | confirmed | allocated | purchased | shipped | invoiced | cancelled`
- `line_status`: `open | allocated | purchased | shipped | invoiced | cancelled`
- `invoice_line_status`: `uninvoiced | partially_invoiced | invoiced | cancelled`
- `result_status`: `not_filled | filled | partially_filled | substituted`

Direction（固定語彙）:
- `input | derived | generated | validation | output_rule`

Entry Method（normalized 固定語彙）:
- `manual | lookup_select | auto_default | auth_context | system_timestamp | rule_engine | calculated | n/a`

用語定義（最終統一）:
- `input`: クライアント/ユーザーが送る入力値
- `derived`: マスタ/認証情報/既存データから導出される値
- `generated`: サーバが新規発行する値（ID・採番・タイムスタンプ等）
- `unit_cost`: 仕入結果の初期記録単価（暫定）
- `final_unit_cost`: 請求前レビュー後の確定仕入単価（最終値）
- `invoiceable_flag`: 請求対象に含めてよいかを示すフラグ
- `result_status`: 仕入結果確定状態（`not_filled|filled|partially_filled|substituted`）

---

## 2) API I/O 定義（主要）

## 2.1 Create Order
- Endpoint: `POST /api/orders`

Request fields:
- `customer_id` (int, required, lookup_select)
- `customer_name` (string, derived)
- `customer_address` (string, derived)
- `order_datetime` (datetime, required)
- `delivery_type` (string, required)
- `delivery_date` (date, required)
- `delivery_note` (string, optional)
- `order_status` (enum, derived)
- `billing_customer_id` (int, required, lookup_select)
- `billing_address` (string, derived)
- `order_source` (string, optional)
- `cutoff_datetime` (datetime, derived)
- `created_at` (datetime, generated)
- `created_by` (string/int, derived from auth_context)
- `updated_at` (datetime, generated)
- `updated_by` (string/int, derived from auth_context)
- `items[]` (required, min 1)
  - `product_id` (int, required)
  - `ordered_qty` (decimal(12,2), required, >0)
  - `order_uom_type` (`uom_count`|`uom_kg`, productから自動反映)
  - `estimated_weight_kg` (decimal(12,3), optional)
  - `price_ceiling` (decimal(12,2), optional)
  - `stockout_policy` (enum, optional)
  - `comment` (string, optional)
  - `line_status` (enum, derived)

Notes:
- `pricing_basis` は `product_id` から自動決定（requestでは受け付けない）
- `unit_price_uom_count` / `unit_price_uom_kg` は受注作成時には入力不要
- `actual_weight_kg` は受注作成時には入力しない（仕入結果登録時に確定）
- tax関連項目は受注時には扱わない（請求時に適用）

Response fields:
- `order_id` (int)
- `order_no` (string)
- `item_count` (int)

---

## 2.1.1 Order Change After Cutoff
- `change_reason` (string, required)
- `procurement_list_regeneration` (boolean, required)
- `allocation_preservation_on_regeneration` (boolean, conditional)

Policy:
- cutoff後は order creator / admin のみ変更可
- 変更時は理由必須、監査ログ必須
- 重大変更判定はユーザー判断とする（システム自動判定なし）
- 重大変更で `allocated -> open` に戻したlineは再生成対象に含める
- 再生成は同一orderで同時実行不可（実行中は `409 Conflict`）
- 再生成失敗時は全体ロールバック（状態不変）

---

## 2.2 Allocation Override
- Endpoint: `PATCH /api/allocations/{allocation_id}/override`

Request fields:
- `final_supplier_id` (int, required)
- `final_qty` (decimal(12,3), required, >0)
- `final_uom` (string, required)
- `target_price` (decimal(12,2), optional)
- `stockout_policy` (enum, optional)
- `comment` (string, optional)
- `override_reason_code` (string, optional)
- `override_note` (string, optional)
- `overridden_by` (string, derived from authenticated user; request input not accepted)

Response fields:
- `ok` (bool)
- `allocation_id` (int)

---

## 2.3 Allocation Split Line
- Endpoint: `POST /api/allocations/{allocation_id}/split-line`

Request fields:
- `parts[]` (required, min 2)
  - `final_supplier_id` (int, required)
  - `final_qty` (decimal(12,3), required)
  - `final_uom` (string, required)
- `override_reason_code` (optional)
- `override_note` (optional)
- `overridden_by` (derived from authenticated user; request input not accepted)

Validation:
- `sum(parts.final_qty) == parent allocation qty`
- UOM consistency check

Response fields:
- `split_group_id` (string)
- `allocation_ids` (int[])

---

## 2.4 Purchase Result Registration
- Endpoint: `POST /api/purchase-results`（実装予定）

Request fields:
- `allocation_id` (int, required)
- `supplier_id` (int, required)
- `purchased_qty` (decimal(12,3), required)
- `purchased_uom` (string, required)
- `actual_weight_kg` (decimal(12,3), optional)
- `unit_cost` (decimal(12,2), optional; 初期記録の暫定単価)
- `final_unit_cost` (decimal(12,2), optional; 請求前レビュー後の確定単価)
- `currency` (string(3), optional default JPY, purchase currency)
- `result_status` (enum, required: `not_filled|filled|partially_filled|substituted`)
- `shortage_qty` (decimal(12,3), derived)
- `shortage_policy` (enum, conditional: `backorder|cancel|substitute|split`)
- `shortage_reason_code` (enum, conditional: `stockout|quality_issue|delivery_delay|supplier_reject|manual_adjustment`)
- `shortage_note` (string, conditional; required when `shortage_reason_code=manual_adjustment`)
- `comment` (optional)

Response fields:
- `purchase_result_id` (int)
- `result_status` (enum)
- `invoiceable_flag` (bool)
- `invoice_block_reason` (string, nullable)

---

## 2.5 Invoice Create / Finalize
- Endpoints:
  - `POST /api/invoices`
  - `POST /api/invoices/{id}/finalize`

Create request fields:
- `order_id` (int, required)
- `invoice_no` (string, required)
- `invoice_date` (date, required)
- `delivery_date` (date, required)
- `invoice_customer_id` (int, required)
- `invoice_customer_name` (string, derived)
- `invoice_customer_address` (string, derived)
- `payment_terms` (string, optional)
- `due_date` (date, required)
- `tax_rate` (decimal, required)
- `tax_amount` (decimal, calculated as `floor(total_amount_pretax × tax_rate)`)
- `total_amount_pretax` (decimal, calculated)
- `total_amount` (decimal, calculated)
- `currency` (string(3), default HKD)

Invoicing unit policy:
- Base unit is order-level invoicing.
- Split invoicing is allowed (multiple invoices per order).
- Invoice line selection is explicit per run; non-selected lines remain uninvoiced.
- Uninvoiced lines can later be invoiced when filled, or remain excluded if cancelled.

Order transition execution policy (MVP):
- Order-level status transition is executed only by explicit user-triggered bulk action.
- Same-day repeated transition runs are allowed.
- No automatic order-status promotion from line aggregation.
- Bulk cancel of unfinished lines is executed only by explicit user input.
- If no eligible lines are found at run time, return `409 STATUS_NO_TARGET_LINES`. 

Finalize hard-stops:
- no selected invoiceable lines
- selected lines include `invoiceable_flag=false`
- selected lines include `result_status=not_filled`
- catch-weight line missing `actual_weight_kg`
- required unit price missing
- invalid billable qty (`billable_qty <= 0` or exceeds uninvoiced remainder)
- tax mismatch against invoice-level formula (`floor(total_amount_pretax × tax_rate)`)
- total mismatch (`total_amount != total_amount_pretax + tax_amount`)
- negative total values
- optimistic lock/version conflict on selected lines

Finalize response fields:
- `invoice_id` (int)
- `status` (`finalized`)
- `sales_unit_price` (decimal(12,2), required)
- `unit_cost_basis` (decimal(12,2), required/internal)
- `gross_margin_rate` (decimal(8,4), optional/internal)
- `updated_invoice_line_status[]` (`partially_invoiced` or `invoiced`)

Reset-to-draft endpoint (MVP):
- `POST /api/invoices/{id}/reset-to-draft`
- Actor: Admin only
- Allowed only when `invoice.status=finalized`

Reset request fields:
- `reset_reason_code` (required: `data_error|pricing_error|tax_error|customer_change|policy_exception`)
- `reset_note` (optional; required when `reset_reason_code=policy_exception`)

Reset behavior:
- `invoice.status: finalized -> draft`
- on cancel/reset operations, related `line_status` and `invoice_line_status` are updated together
- affected `invoice_line_status` is uniformly reset to `uninvoiced`
- hard-stop on non-finalized invoice / missing reason / version conflict
- hard-stop failure does not lock record; users can fix and retry

Unlock endpoint (MVP):
- `POST /api/invoices/{id}/unlock`
- Actor: Admin only
- Allowed only when `invoice.status=finalized` and invoice is locked

Unlock request fields:
- `unlock_reason_code` (required: `pricing_correction|quantity_correction|tax_correction|customer_request|data_fix|other`)
- `reason_note` (optional, <= 500 chars)

Unlock behavior:
- unlocks finalized invoice for admin edits
- no auto-expiry (TTL unlimited)
- no auto re-lock; re-finalize is used to freeze again
- hard-stop on missing reason / invalid reason / status mismatch / version conflict

---

## 3) 帳票 I/O 定義

## 3.1 発注リスト（By Supplier）CSV
Filename example:
- `purchase_list_YYYYMMDD_supplier_<id>.csv`

Columns:
- `batch_id`
- `supplier_id`
- `supplier_name`
- `order_no`
- `customer_name`
- `product_sku`
- `product_name`
- `ordered_qty`（受注数量）
- `ordered_uom_type`
- `final_qty`（発注数量）
- `final_uom`
- `target_price`
- `stockout_policy`
- `comment`

---

## 3.2 納品/仕入結果入力用CSV（任意）
Columns:
- `allocation_id`
- `supplier_id`
- `purchased_qty`
- `purchased_uom`
- `actual_weight_kg`
- `unit_cost`
- `final_unit_cost`
- `result_status`
- `comment`

---

## 粗利計算ルール（内部）
- `gross_margin_rate = (sales_unit_price - unit_cost_basis) / unit_cost_basis`
- split仕入れ時の `unit_cost_basis` は加重平均:
  - `Σ(purchased_qty_i × final_unit_cost_i) / Σ(purchased_qty_i)`
- 請求行は `billable_qty` / `billable_uom` を基準に算出する
- `gross_margin_rate` は内部項目であり、請求書PDFには出力しない

## 3.3 請求書PDF（顧客向け）
Header fields:
- `invoice_no`
- `invoice_date`
- `delivery_date`
- `customer_name`
- `currency`（HKD）

Line fields:
- `description`
- `qty_display`
- `uom_display`
- `weight_kg`（catch-weight時）
- `unit_price`
- `amount`
- `tax_amount`

Totals:
- `subtotal`
- `tax_total`（invoice totalに対して課税し、`floor`で丸め）
- `grand_total`

Not printed on PDF:
- `gross_margin_rate`（内部項目のため非表示）

---

## 4) バリデーションI/O（エラー設計）

標準エラー形式:
- `code` (string)
- `message` (string)
- `field` (string, optional)
- `detail` (object/string, optional)

主なHTTP:
- `401` 認証不足
- `403` 権限不足
- `409` ステータス競合/遷移不可
- `422` 入力値不正

---

## 5) 確定事項（2026-03-16 updated）
- `delivery_date` はAPI必須項目（Defaultは注文日の翌日、手動変更可）
- `override_reason_code` は任意（override時の理由入力は必須ではない）
- `target_price` は通常は任意。ただし `override_reason_code=better_price` または `urgent_delivery` の場合は必須
- supplier は自分の担当行に限り `final_unit_cost` を更新可（監査ログ必須）。ただし請求確定前に buyer/admin が最終確認を行う
- 税は invoice total に対して課税し、`floor(total_amount_pretax × tax_rate)` で丸める
- shortage処理は `backorder|cancel|substitute|split` を許可
- shortage reason code は `stockout|quality_issue|delivery_delay|supplier_reject|manual_adjustment`
- `manual_adjustment` をMVPで許可（`shortage_note` 必須）
- `delivery_delay` は全選択肢（backorder限定なし）
- `quality_issue` は優先ポリシーなし

## 6) Reason code sets (final unified)
- `cancel_reason_code`:
  - `customer_cancelled | stockout_unresolved | data_error | duplicate_order | policy_exception`
- `reset_reason_code` (required):
  - `data_error | pricing_error | tax_error | customer_change | policy_exception`
  - `reset_note` is required when `reset_reason_code=policy_exception`
- `unlock_reason_code` (required):
  - `pricing_correction | quantity_correction | tax_correction | customer_request | data_fix | other`
  - `reason_note` is optional
