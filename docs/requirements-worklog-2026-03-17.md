# 要件定義 作業ログ（2026-03-17）

対象プロジェクト: `order_system`
作成者: OpenClawBot

---

## 本日の目的
- 仕様表記・enum統一の最終化
- 状態遷移条件の厳密化
- Cancel / Reset / Unlock 境界仕様の確定
- UAT実行テンプレの数値固定
- MVP要件定義のクローズ宣言（v2）

---

## 実施内容（要約）

1. **用語・項目名統一（Phase 3）**
- `uom_count / uom_kg` へ統一
- `unit_price_uom_count / unit_price_uom_kg` へ統一
- `unit_cost`（暫定）/ `final_unit_cost`（確定）定義を明文化
- `input / derived / generated` 定義をI/O仕様へ追記

2. **OpenAPI / MD 差分補正**
- business rule文言の `partial` を `split` に補正
- OpenAPI skeleton に価格項目を追記
- 項目名差分の残件を解消

3. **状態遷移仕様の厳密化**
- line先行更新・order一括実行（ユーザー入力トリガー）方針を確定
- 同一営業日で複数回の一括遷移を許可
- lineはcancelされるまで元orderに所属
- 一括キャンセルは明示入力時のみ実行（自動実行なし）

4. **Cancel / Reset / Unlock 境界仕様確定**
- Cancel時は `line_status` と `invoice_line_status` を同時更新
- Reset対象は `invoice.status=finalized` のみ
- Unlock対象は finalized+locked invoice、Admin限定、reason必須

5. **エラー / OpenAPI / UAT 同期**
- `STATUS_NO_TARGET_LINES` を追加
- user-triggered order bulk transition endpointをOpenAPIに反映
- UATに遷移/Unlock境界ケースを追加

6. **UAT実行テンプレ数値固定**
- 同時ユーザー: 10
- orders: 10,000 / order_lines: 100,000 / invoices: 30,000
- API P95: 1.5s / グリッドP95: 2.0s / allocation 5,000 lines: 5分以内

7. **実装雛形計画作成**
- `implementation-bootstrap-plan.md` を作成
- フォルダ構成、初期タスク、Done条件を定義

8. **クローズ宣言**
- `requirements-definition-closure-v2.md` を新規作成
- MVP要件定義クローズを宣言

---

## 本日作成/更新した主ファイル
- `docs/requirements-definition-closure-v2.md`
- `docs/implementation-bootstrap-plan.md`
- `docs/uat-acceptance-checklist-draft.md`
- `docs/status-transition-draft.md`
- `docs/report-and-api-io-definition-draft.md`
- `docs/invoice-lock-and-concurrency-draft.md`
- `docs/invoice-rules-draft.md`
- `docs/api-error-codes-draft.md`
- `docs/openapi-error-components-draft.yaml`
- `docs/openapi-mvp-skeleton-draft.yaml`
- `docs/decision_logs.txt`

---

## 備考
- 要件定義は実装ハンドオフ可能な状態まで到達。
- 残タスクは主に実装フェーズ管理（環境準備・負荷試験・UAT実行）。
