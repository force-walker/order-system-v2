# UAT 受け入れ基準チェックリスト Draft (MVP)

Updated: 2026-03-17

## 目的
本番リリース可否を、業務シナリオ単位で Go / No-Go 判定できるようにする。

判定ルール:
- 各シナリオの必須チェックが **すべてPASS** であること
- Critical不具合（業務停止・金額不整合・監査欠落）が **0件**

## 前提データ/負荷プロファイル（固定）
- 同時ユーザー数（ピーク）: **10**
- 対象データ量:
  - orders: **10,000**
  - order_lines: **100,000**
  - invoices: **30,000**
- 性能しきい値:
  - 一般API P95: **1.5秒以内**
  - 主要グリッド初期表示 P95: **2.0秒以内**
  - allocation batch: **5,000 lines / 5分以内**

## 実行記録テンプレート（各ケース共通）
- Case ID:
- 実施日時:
- 担当者:
- 期待結果:
- 実結果:
- 判定: PASS / FAIL
- 証跡: スクリーンショットURL / ログID / trace_id
- 備考:

---

## 1) 受注入力（Order Entry）

### UAT-O1: 受注新規登録（通常商品）
- [ ] `POST /api/orders` で受注作成できる
- [ ] 必須項目不足時に 422 が返る
- [ ] `ordered_qty > 0` バリデーションが効く
- [ ] 保存後、order/itemがDBで整合している

### UAT-O2: catch-weight商品登録
- [ ] `pricing_basis=uom_kg` 時、価格/重量条件が検証される
- [ ] 見込み重量/実重量ロジックが仕様通り動く

合格条件:
- [ ] 受注系の正常/異常が仕様通り

---

## 2) 配分（Allocation）

### UAT-A1: 自動配分
- [ ] `run-auto` 実行で対象明細が配分される
- [ ] 未配分・不正値が警告に出る

### UAT-A2: 手動override
- [ ] supplier/qty/uom変更が反映される
- [ ] `override_reason_code` は任意で入力可能（未入力でも保存可能）
- [ ] audit log に who/when/before/after/why が残る

### UAT-A3: split-line
- [ ] 2件以上に分割可能
- [ ] 子qty合計≠親qtyでエラーになる
- [ ] UOM不一致でエラーになる
- [ ] split_group_id / parent-child 関係が保存される

### UAT-A4: 配分確定
- [ ] 不正allocationを含むと確定ブロックされる
- [ ] split-group整合性チェックが有効

合格条件:
- [ ] 配分の正常/異常フローを現場想定で再現できる

---

## 3) 仕入結果登録（Purchase Result）

### UAT-P1: 仕入結果登録
- [ ] full/partial/failed/substitute を登録できる
- [ ] purchased_qty/uom が保存される
- [ ] supplier表示・対象絞り込みが可能

### UAT-P2: 最終仕入単価
- [ ] `final_unit_cost` を入力/更新できる
- [ ] 変更履歴が監査に残る

合格条件:
- [ ] 仕入結果が請求前提データとして利用可能

---

## 4) 請求（Invoice）

### UAT-I1: 請求作成
- [ ] `POST /api/invoices` で請求作成できる
- [ ] `uom_count` + `uom_kg` 混在計算が正しい
- [ ] 行税計算・値引き順序が仕様通り

### UAT-I2: 請求確定ハードストップ
- [ ] catch-weightで `actual_weight_kg` 無しは確定不可
- [ ] required price無しで確定不可
- [ ] 合計マイナスで確定不可

### UAT-I3: ステータス遷移
- [ ] `shipped -> invoiced` が成立
- [ ] orderステータス遷移はユーザー一括実行時のみ行われる（自動昇格しない）
- [ ] 同一営業日の複数回一括実行が可能
- [ ] 遷移対象lineが0件の場合に `409 STATUS_NO_TARGET_LINES` が返る
- [ ] 未完lineの一括キャンセルは明示入力時のみ実行される
- [ ] `invoiced` 以降のcancelがMVPルール通り制御される

### UAT-I4: Unlock / Reset 境界
- [ ] reset-to-draft は `invoice.status=finalized` のときのみ実行可能
- [ ] unlock は `invoice.status=finalized` かつ lock済みinvoiceのみ実行可能
- [ ] unlock は Adminのみ実行可能
- [ ] `unlock_reason_code` 必須、`reason_note` は任意（500文字以内）
- [ ] unlock 後は Admin編集可、re-finalizeで再確定できる

合格条件:
- [ ] 請求金額が業務期待値と一致し、誤請求が発生しない

---

## 5) RBAC / API認可

### UAT-R1: ロール別アクセス
- [ ] admin: 全操作可能
- [ ] order_entry: 受注/請求可能
- [ ] buyer: 配分/発注可能
- [ ] supplier: 自分の対象結果のみ更新可能
- [ ] customer: 自分の荷受確認のみ可能

### UAT-R2: 認可エラー
- [ ] 未認証は 401
- [ ] 権限不足は 403
- [ ] 遷移競合は 409

合格条件:
- [ ] 権限外操作が全て遮断される

---

## 6) 帳票/入出力

### UAT-D1: 発注CSV
- [ ] 必須列が定義どおり出力される
- [ ] supplier単位で出力できる

### UAT-D2: 請求PDF
- [ ] ヘッダ/明細/合計の項目が定義どおり
- [ ] catch-weight表示が仕様通り

### UAT-D3: API I/O整合
- [ ] `report-and-api-io-definition-draft.md` と差異がない

合格条件:
- [ ] 帳票/APIの項目不一致がない

---

## 7) 非機能

### UAT-N1: 性能
- [ ] 配分runが目標時間内（5,000 lines / 5分以内）
- [ ] グリッド初期表示P95が2.0秒以内
- [ ] 一般API P95が1.5秒以内

### UAT-N2: 監査/運用
- [ ] critical操作の監査ログ欠落なし
- [ ] 障害時のログ追跡が可能

### UAT-N3: バックアップ/復旧
- [ ] バックアップ取得確認
- [ ] 復元手順で最低1回リハーサル済み

合格条件:
- [ ] 運用開始後に継続稼働できる裏付けあり

---

## 8) Go / No-Go 判定

### Go 条件（全て満たす）
- [ ] 主要UATシナリオ PASS率 100%（必須項目）
- [ ] Critical障害 0件
- [ ] 金額・税・重量の整合性問題 0件
- [ ] 監査ログ欠落 0件
- [ ] 運用責任者（受注/発注/請求）承認済み

### No-Go 条件（いずれか該当）
- [ ] 誤請求の可能性が残る
- [ ] 権限漏れで不正操作が可能
- [ ] 監査証跡が不足
- [ ] 復旧手順未検証

---

## 9) サインオフ
- 受注責任者: __________________
- 発注責任者: __________________
- 請求責任者: __________________
- システム管理者: ______________
- 日付: ________________________
