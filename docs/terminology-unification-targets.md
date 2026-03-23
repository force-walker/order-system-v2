# Terminology Unification Targets (Status Vocabulary)

Updated: 2026-03-16
Purpose: 仕様書更新前に対象ドキュメントを固定し、進捗を管理する。

## Canonical Status Vocabulary (fixed)

- `order_status`: `new -> confirmed -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- `line_status`: `open -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- `invoice_line_status`: `uninvoiced | partially_invoiced | invoiced | cancelled`

---

## Must (必ず整合)

1. `docs/status-transition-draft.md`  
   - 遷移の一次定義（基準）
2. `docs/report-and-api-io-definition-draft.md`  
   - enum記載の基準
3. `docs/db-dual-uom-draft.md`  
   - DB enum / 制約定義
4. `docs/requirements-definition-closure-v1.md`  
   - クローズ宣言の整合
5. `docs/decision_logs.txt`  
   - 最終意思決定の証跡

## Should (追随)

6. `docs/api-authorization-spec-draft.md`
7. `docs/business-rules-decision-table-draft.md`
8. `docs/uat-acceptance-checklist-draft.md`
9. `docs/spec-package-index.md`

---

## Progress Snapshot

- ✅ Updated (Phase 1)
  - `requirements-definition-closure-v1.md`
  - `api-authorization-spec-draft.md`
  - `business-rules-decision-table-draft.md`
  - `uat-acceptance-checklist-draft.md`
  - `decision_logs.txt`

- ✅ Already aligned (no status terminology change needed)
  - `status-transition-draft.md`
  - `report-and-api-io-definition-draft.md`
  - `db-dual-uom-draft.md`

- ✅ Completed (Enum unification)
  - `stockout_policy`: `backorder | substitute | cancel | split` に統一
  - `override_reason_code`: optional に統一
  - cancel/reset/unlock reason code セットを最終一致確認

- ✅ Completed (Terminology phase 3)
  - `uom_count / uom_kg` 表記へ統一（spec docs）
  - `unit_price_uom_count / unit_price_uom_kg` 命名へ統一
  - `unit_cost`（暫定） / `final_unit_cost`（確定）の責務を明文化
  - `input / derived / generated` 定義を明文化

- ⏭ Next scope (separate task)
  - API/YAMLの enum/field 名称の最終同期（実装前の差分ゼロ確認）
