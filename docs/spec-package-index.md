# Order Input System — Spec Package (Draft A)

Created: 2026-02-25
Updated: 2026-03-05

## Included Documents

1. `docs/db-dual-uom-draft.md`
   - Dual unit-of-measure data model draft
   - Catch-weight support columns and validations
   - Allocation split-line / target-price / stockout-policy / final unit-cost extensions

2. `docs/allocation-flow-draft.md`
   - Auto supplier allocation flow
   - Manual override workflow and safety controls
   - Unified multi-grid design (By Supplier / By Customer / By Product)

3. `docs/invoice-rules-draft.md`
   - Billing rules for mixed piece + per-kg invoices
   - Finalization constraints and rounding policy

4. `docs/flowchart-stakeholders.md`
   - End-to-end role flow (受注入力者 / 発注者 / 仕入れ先 / 販売先)
   - Role responsibilities and key inputs/outputs

5. `docs/status-transition-draft.md`
   - Lifecycle transition definition
   - MVP terminal status = `invoiced` (`completed` removed)
   - `paid` deferred to future accounting scope

6. `docs/exception-cases-draft.md`
   - Exception scenarios (partial, stockout, substitute, catch-weight blocking, etc.)
   - Required actions and audit requirements

7. `docs/non-functional-requirements-draft.md`
   - Performance/availability/security/audit/backup/operations requirements
   - MVP service quality and operational baselines

8. `docs/rbac-draft.md`
   - Role-based access control matrix (Admin / 受注入力者 / 発注者 / 仕入先 / 販売先)
   - Function-level create/update/confirm/cancel permissions

9. `docs/business-rules-decision-table-draft.md`
   - Decision priority table and final approver mapping
   - Conflict resolution order and approval thresholds

10. `docs/api-authorization-spec-draft.md`
   - Endpoint-level authorization policy by role
   - Scope rules, audit requirements, and auth error semantics

11. `docs/report-and-api-io-definition-draft.md`
   - 帳票（CSV/PDF）とAPIのI/O項目定義
   - 必須/型/コード値/エラー設計の統一

12. `docs/uat-acceptance-checklist-draft.md`
   - UATシナリオ別の受け入れ判定チェックリスト
   - Go / No-Go 判定条件とサインオフ項目

## Scope
This package is draft-level functional specification for MVP planning and implementation handoff.

## Next Recommended Step
- Confirm business rule details:
  - tax rounding policy
  - override reason code list
  - stockout policy code list
  - target price mandatory/optional rule
  - cutoff timing and lock/unlock policy
- Then convert into implementation-ready artifacts:
  - SQL migrations
  - API contract
  - screen wireframes (3-grid unified schema)

13. `docs/requirements-definition-closure-v1.md`
   - MVP要件定義のクローズ宣言
   - 未確定項目の最終決定（delivery_date/target_price/final_unit_cost）

14. `docs/permission-change-policy.md`
   - 権限変更の原則と運用手順
   - supplier入力補助 / buyer最終validation方針と将来拡張パターン

15. `docs/IO_from_order_to_invoice.xlsx`
   - Order→InvoiceのI/Oマトリクス（Excel版）
   - 入力/出力/継承元 + Allowed values / Validation rule / System of record

16. `docs/invoice-lock-and-concurrency-draft.md`
   - Invoice更新ロック基準、採番、楽観ロック、再読込フロー、all-or-nothing境界

17. `docs/api-error-codes-draft.md`
   - HTTPステータスと業務エラーコードの標準定義
   - Invoice/Allocation/Regenerationの主要エラー対応とレスポンス形式

18. `docs/openapi-error-components-draft.yaml`
   - OpenAPI 3.0 の再利用可能なエラー components 定義
   - ErrorResponse schema / 共通responses(400/401/403/404/409/422) / finalize endpoint例

19. `docs/openapi-mvp-skeleton-draft.yaml`
   - orders / allocations / purchase-results / invoices のMVP OpenAPI骨子
   - 各endpointに標準エラーレスポンスを適用した実装下書き

20. `docs/terminology-unification-targets.md`
   - 表記統一作業の対象ドキュメント（Must/Should）と進捗管理
   - status語彙のcanonical定義と適用状況

21. `docs/implementation-bootstrap-plan.md`
   - 推奨スタック前提の実装立ち上げ計画
   - フォルダ構成、初期タスク、Done条件、リスク

22. `docs/requirements-definition-closure-v2.md`
   - MVP要件定義クローズ宣言（v2）
   - v1以降の確定差分、実装引き渡し基準、MVP外項目
