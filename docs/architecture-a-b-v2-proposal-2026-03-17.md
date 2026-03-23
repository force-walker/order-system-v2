# Architecture A/B Proposal (Document-Aligned, MVP v2)

Date: 2026-03-17
Source alignment:
- docs/requirements-definition-closure-v2.md
- docs/status-transition-draft.md
- docs/db-dual-uom-draft.md
- docs/non-functional-requirements-draft.md

## A. システム構成案（文書整合版）

### 1. 全体アーキテクチャ（MVP）
- Frontend (Web SPA)
  - 受注入力、配分確認、仕入結果入力、請求確定、監査ログ閲覧
- Backend API (REST / `/api/v1`)
  - 認証・認可（RBAC）
  - ステータス遷移実行（ユーザー明示バルク実行）
  - サーバー側金額/税計算（authoritative）
- Batch/Worker
  - 配分処理（最大5,000行/5分目標）
  - 請求バッチ生成（大量処理）
- DB (PostgreSQL)
  - 業務トランザクション（orders, allocations, purchase_results, invoices）
  - 監査ログ（before/after, reason）
- Observability
  - 構造化ログ、メトリクス、Correlation ID、アラート

### 2. 設計原則（既存仕様準拠）
- 状態遷移固定
  - `new -> confirmed -> allocated -> purchased -> shipped -> invoiced (+cancelled)`
  - `paid` はMVP外
- 行ステータス主導
  - 行更新先行
  - 注文ヘッダ遷移は自動昇格しない（明示バルク実行のみ）
- Dual-UOM / Catch-weight 前提
  - `uom_count / uom_kg`
  - `unit_price_uom_count / unit_price_uom_kg`
- エラー標準
  - HTTP `400/401/403/404/409/422`
  - 遷移対象ゼロ時: `409 STATUS_NO_TARGET_LINES`
- 監査
  - cancel / override / reset / unlock は reason code 必須

### 3. 非機能ターゲット（MVP）
- API P95 <= 1.5s
- グリッド初期表示 P95 <= 2.0s
- 配分バッチ 5,000行 <= 5分
- 可用性 99.5%（月次）
- RPO <= 1時間 / RTO <= 4時間

### 4. コンポーネント図（テキスト）
`Client -> API -> PostgreSQL`
`API -> Worker(Allocation/Invoice Batch) -> PostgreSQL`
`API/Worker -> Logs/Metrics/Alert`

## B. ERD草案（Dual-UOM反映版）

### 1. 主要テーブル
1. products
   - `sku`(uniq), `order_uom`, `purchase_uom`, `invoice_uom`
   - `is_catch_weight`, `pricing_basis_default (uom_count|uom_kg)`
2. orders
   - `order_no`(uniq), `customer_id`, `delivery_date`, `status`
3. order_items
   - `order_id`, `product_id`, `ordered_qty`
   - `order_uom_type (uom_count|uom_kg)`
   - `estimated_weight_kg`, `actual_weight_kg`
   - `pricing_basis (uom_count|uom_kg)`
   - `unit_price_uom_count`, `unit_price_uom_kg`
   - `line_status (open|allocated|purchased|shipped|invoiced|cancelled)`
4. supplier_allocations
   - `order_item_id`, `suggested_supplier_id`, `final_supplier_id`
   - `suggested_qty/final_qty`, `is_manual_override`, `override_reason_code`
   - `target_price`, `stockout_policy (backorder|substitute|cancel|split)`
5. purchase_results
   - `allocation_id`, `supplier_id`, `purchased_qty`, `actual_weight_kg`
   - `unit_cost`, `final_unit_cost`, `result_status`
   - `shortage_qty`, `shortage_policy`, `invoiceable_flag`
6. invoices
   - `invoice_no`(uniq), `customer_id`, `invoice_date`, `delivery_date`
   - `status (draft|finalized|sent|cancelled)`, `subtotal/tax_total/grand_total`
7. invoice_items
   - `invoice_id`, `order_item_id`, `billable_qty`, `billable_uom`
   - `invoice_line_status (uninvoiced|partially_invoiced|invoiced|cancelled)`
   - `sales_unit_price`, `unit_cost_basis`, `line_amount`, `tax_amount`
8. audit_logs
   - `entity_type`, `entity_id`, `action`, `before_json`, `after_json`, `reason_code`

### 2. リレーション
- orders 1 - N order_items
- products 1 - N order_items
- order_items 1 - N supplier_allocations
- supplier_allocations 1 - N purchase_results
- invoices 1 - N invoice_items
- order_items 1 - N invoice_items（分割請求対応）
- 重要更新は audit_logs に記録

### 3. 主要制約・バリデーション
- `orders.order_no` / `products.sku` / `invoices.invoice_no` UNIQUE
- `ordered_qty > 0`
- `pricing_basis=uom_kg` の場合 `unit_price_uom_kg` 必須
- `pricing_basis=uom_count` の場合 `unit_price_uom_count` 必須
- catch-weight品は請求確定時 `actual_weight_kg` 必須
