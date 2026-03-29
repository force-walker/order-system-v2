# progress_daily_2026-03-28
Channel: #08-progress-daily (1486715138793930812)
Purpose: 昨日〜今日の進捗履歴を集約記録

## 対象期間
- 昨日: 2026-03-27
- 今日: 2026-03-28

---

## backend / #03

### 2026-03-27

#### バリデーション境界強化（PR #18）
- 追加テスト: `backend/tests/test_validation_boundaries_api.py`
- 主な強化点:
  - enum 全値/未知値、空文字、桁・長さ、負数/0、日付前後、遷移from/to境界
  - unknown enum/空文字/長すぎる値は 422
  - 0/負数は 422
  - `due_date < invoice_date` は 422
  - 遷移系 same status / invalid pair / unknown enum は 422、valid pair は 200
- schema制約強化:
  - order: `customer_id > 0`, `note` max length
  - invoice: `order_id > 0`
  - allocation: supplier_id/uom/reason_code/note 境界
  - purchase_result: allocation_id/uom/result_status/note 境界
- 検証: pytest 42 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/18>

#### 監査ログ/メトリクス運用品質改善（PR #19）
- 共通 `write_audit_log` 追加
- mutating endpoint の監査ログ統一
  - products/customers create/update
  - orders create/bulk-transition
  - invoices create/finalize/reset-to-draft/unlock
  - allocations override/split-line
  - purchase-results create/update/bulk-upsert
- `metrics_summary` 拡張
  - errors4xxTotal/errors5xxTotal/statusFamilyCounts/endpointStatusCounts/endpointLatencyP95Ms
- docs更新: `docs/architecture/07-observability.md`
- テスト拡張: `backend/tests/test_audit_metrics_api.py`
- 検証: pytest 43 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/19>

#### DB整合性の最終ガード（PR #20）
- DB制約追加:
  - order_items: `ordered_qty > 0`
  - supplier_allocations: `final_qty IS NULL OR final_qty > 0`
  - purchase_results: `purchased_qty > 0` + `allocation_id UNIQUE`
  - invoices: `due_date >= invoice_date` + 合計金額非負
  - batch_jobs: 各カウンタ非負、`max_retries >= 1`、`retry_count <= max_retries`
- migration: `2026032701_add_integrity_constraints.py`
- purchase-results 重複時 409 を明示
- docs更新: `docs/architecture/04-db-core-tables.md`
- 検証: pytest/ruff pass + clean DB migration `2026032701 (head)`
- PR: <https://github.com/force-walker/order-system-v2/pull/20>

#### 例外ハンドリング共通化（PR #21）
- `IntegrityError` / `SQLAlchemyError` の global handler 追加
- `app/core/exception_mapping.py` で一元マッピング
  - unique -> 409 `RESOURCE_ALREADY_EXISTS`
  - FK -> 422 `INVALID_REFERENCE`
  - check/not-null/length -> 422 `VALIDATION_FAILED`
  - その他 integrity -> 409 `CONSTRAINT_VIOLATION`
- テスト: `backend/tests/test_exception_mapping.py`
- docs更新: `docs/api-error-codes-draft.md`
- 検証: pytest 46 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/21>

#### OpenAPI最終同期（PR #22）
- `docs/openapi-mvp-skeleton-draft.yaml` を runtime spec（`/openapi.json`）で再生成
- 差分解消（paths/schemas/responses）
- 検証: `tests/test_openapi_contract_api.py` pass
- PR: <https://github.com/force-walker/order-system-v2/pull/22>

#### 監査ログ標準化（PR #23、#22 merge後）
- `AuditAction` 定数で語彙統一
- 非認証endpointの既定actorを `system_api` に統一
- batch route も共通 `write_audit_log` 利用
- docs: `docs/architecture/08-audit-api.md`
- テスト更新（action/actor 標準化）
- 検証: pytest 46 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/23>

#### metrics summary 固定スキーマ化（PR #24、#23 merge後）
- `/api/v1/ops/metrics/summary` を response_model 化
- `backend/app/schemas/metrics.py` 追加
- top-level keys固定: `timestamp/api/worker/db`
- api keys固定: `requestsTotal,errorRate5xx,errors4xxTotal,errors5xxTotal,statusFamilyCounts,p95LatencyMs,endpointLatencyP95Ms,endpointStatusCounts,inflightRequests`
- docs更新: `docs/architecture/07-observability.md`
- 検証: pytest 46 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/24>

#### 回帰テスト強化 + 最小インデックス改善（PR #25/#26）
- PR #25: `test_api_regression_matrix.py`
  - core endpoint の success/409/422/404 をマトリクス検証
  - 検証: pytest 49 passed, ruff all passed
- PR #26: 最小インデックス追加
  - batch hot path: `(job_type, business_date, status)`
  - audit timeline/actor: `(entity_type, entity_id, changed_at)`, `(changed_by, changed_at)`
  - migration: `2026032702_add_perf_indexes.py`
  - 検証: clean DB migration `2026032702 (head)`

#### Frontend handoff資料 + seed導線（PR #27）
- `docs/frontend-api-contract-freeze-2026-03.md`
- `docs/frontend-mockup-dev-quickstart.md`
- `backend/scripts/seed_frontend_mock_data.py`（idempotent）
- 検証: pytest 49 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/27>

#### Bulk API基盤（products）（PR #28）
- endpoint追加:
  - `POST /api/v1/products/bulk/create`
  - `PATCH /api/v1/products/bulk/update`
  - `POST /api/v1/products/bulk/upsert`
  - `DELETE /api/v1/products/bulk/delete`
- 部分失敗レスポンス:
  - `summary: { total, success, failed }`
  - `errors[]: { index, itemRef, code, message }`
- テスト: `backend/tests/test_products_bulk_api.py`
- 検証: pytest 51 passed, ruff all passed
- PR: <https://github.com/force-walker/order-system-v2/pull/28>

### 2026-03-28

#### 要件ズレ修正（連続実施）
- PR #34: orders `order_no` 自動採番化
  - create時の手入力廃止、`ORD-<timestamp>-<suffix>` 自動生成
  - UNIQUE衝突時リトライ（最大5回）
  - 検証: pytest 51 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/34>

- PR #35: customers `code` -> `customer_code` 統一
  - DB/API/schema/route/test/seed 更新
  - migration: `2026032801_rename_customer_code.py`
  - clean DB migration: `2026032801 (head)`
  - <https://github.com/force-walker/order-system-v2/pull/35>

- PR #37: order_items 不足列 + pricing_basis 制約
  - 追加列: `order_uom_type`,`estimated_weight_kg`,`actual_weight_kg`
  - CHECK: pricing_basis別の必須価格
  - migration: `2026032802_add_order_item_uom_weight_and_checks.py`
  - 検証: pytest 53 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/37>

- PR #38: allocations 不足列 + split linkage
  - 追加列: `suggested_supplier_id`,`suggested_qty`,`target_price`,`parent_allocation_id`,`is_split_child`
  - split-lineで親子linkage・suggested/target引継ぎ
  - migration: `2026032803_add_allocation_linkage_fields.py`
  - 検証: pytest 53 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/38>

- PR #39: purchase_results 不足列
  - 追加列: `supplier_id`,`actual_weight_kg`,`unit_cost`,`final_unit_cost`,`shortage_qty`,`shortage_policy`,`recorded_by`
  - 制約追加（重量>0、コスト/shortage非負）
  - migration: `2026032804_add_purchase_result_fields.py`
  - 検証: pytest 53 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/39>

- PR #40: invoice_items テーブル実装
  - 列: `invoice_id`,`order_item_id`,`billable_qty`,`billable_uom`,`invoice_line_status`,`sales_unit_price`,`unit_cost_basis`,`line_amount`,`tax_amount`
  - 非負制約 + index追加
  - migration: `2026032805_create_invoice_items_table.py`
  - 検証: pytest 55 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/40>

- PR #41: orders `created_by` / `updated_by`
  - default `system_api`
  - create/bulk-transitionで設定更新
  - migration: `2026032806_add_orders_created_updated_by.py`
  - 検証: pytest 55 passed, ruff all passed
  - <https://github.com/force-walker/order-system-v2/pull/41>

---

## frontend / #04（昨日〜今日サマリ）
- PR #29: モック土台（作成→一覧→詳細遷移）
- PR #30: 注文作成フォームUI改善 + バリデーション強化
- PR #32: 一覧/詳細の表示改善（ステータスバッジ・フィルタ）
- PR #33: 最小API接続（dev login/token保持、GET/POST /orders、USE_MOCK切替）
- PR #36: エラーハンドリング統一 + 最小テスト(Vitest)
- 運用: 開発ブランチ→PR→Merge 統一、不要ブランチ整理

---

## 2026-03-28 追記（夜間〜終盤）

### backend / #03（追加分）
- PR #42: `audit_logs` 拡張
  - 追加列: `before_json`, `after_json`, `trace_id`, `request_id`, `job_id`
  - 追加index: `trace_id`, `request_id`, `job_id`
  - 監査書き込み共通関数を拡張（before/after/correlation id）
  - migration: `2026032807_extend_audit_logs_columns.py`
  - 検証: pytest 55 passed, ruff all passed, clean DB migration `2026032807 (head)`
  - PR: <https://github.com/force-walker/order-system-v2/pull/42>

- PR #43: 残差分2件の修正
  - `supplier_allocations.final_qty` を `>= 0` に調整
  - `purchase_results` の `allocation_id UNIQUE` を解除（1-Nへ整合）
  - `purchase_results.result_status` を enum 制約化
  - migrations:
    - `2026032808_relax_final_qty_non_negative.py`
    - `2026032809_align_purchase_results_cardinality_and_status_enum.py`
  - 検証: pytest 55 passed, ruff all passed, clean DB migration `2026032809 (head)`
  - PR: <https://github.com/force-walker/order-system-v2/pull/43>

- PR #44: 最終受け入れチェック表
  - 追加: `docs/backend-final-acceptance-checklist-2026-03-28.md`
  - 要件→実装/テスト/PR対応を1枚化
  - 受入判断: 現要件セットで Backend 受入完了、Frontend再開推奨
  - PR: <https://github.com/force-walker/order-system-v2/pull/44>

- PR #47: 注文明細行保存API
  - 追加API:
    - `GET /api/v1/orders/{order_id}/items`
    - `POST /api/v1/orders/{order_id}/items`
    - `POST /api/v1/orders/{order_id}/items/bulk`
    - `PATCH /api/v1/orders/{order_id}/items/{item_id}`
    - `DELETE /api/v1/orders/{order_id}/items/{item_id}`
  - `order_items.note` 追加（migration: `2026032810_add_order_items_note.py`）
  - bulkは部分失敗レスポンス対応
  - 検証: pytest 57 passed, ruff all passed, clean DB migration `2026032810 (head)`
  - PR: <https://github.com/force-walker/order-system-v2/pull/47>

### testing / QA（追加分）
- 全体回帰を複数回実施（compileall + pytest）
- 回帰拡張方針を整理（clean DB migration / 再起動idempotency / コンテナ内スモーク）
- `scripts/regression_check.sh` の内容確認
- 補足報告:
  - backend回帰テスト件数: 43 → 46 → 49 → 51 → 53 → 55
  - frontend: `npm run build` 成功、`vitest` 2 tests PASS
  - `scripts/regression_frontend.sh` / `scripts/regression_all.sh` を再生成・固定化

## 日次ハイライト
- backendは要件差分解消フェーズを完走し、主要差分の実装・DB整合・API整合・受入チェック表まで完了
- frontendはモック→API接続→エラー統一までの土台を維持し、handoff可能状態
- testing/QAは全体回帰運用を固定化し、frontend含む一体回帰フローを整備
