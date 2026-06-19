# 請求ドラフトページ改修 BE/FE 指示

作成日: 2026-06-19
状態: BE/FE 実装完了・マージ済み

## 背景

- 現在の請求ドラフト一覧は請求書単位の集計表示になっている。
- 以前のように、請求ドラフト一覧で請求明細行を直接見える形に戻したい。
- あわせて、仕入単価・請求単価入力欄・両者から計算される粗利%を一覧上で確認したい。

現状参考:

- FE 一覧画面: `frontend/src/features/orders/pages/InvoiceDraftPage.tsx`
- FE 明細詳細: `frontend/src/features/orders/pages/InvoiceDraftDetailPage.tsx`
- FE API: `frontend/src/features/orders/services/invoiceService.ts`
- BE ドラフト明細一覧 API: `backend/app/api/routes_invoices.py` の `/api/v1/invoices/draft-list`

## 依頼内容

請求ドラフト一覧を「請求書単位の集計表」ではなく「請求明細行ベースの表」に変更する。

一覧ヘッダーは以下を基本とする。

1. チェックボックス
2. 詳細へのリンク
3. 請求ヘッダー番号
4. 取引先名
5. 請求日
6. 納品日
7. ステータス
8. 仕入単価
9. 請求単価
10. 請求数量
11. 請求金額
12. 粗利%

補足:

- 「請求明細行を表示」が主目的なので、1行 = 1請求明細行とする。
- ただしチェックボックスと詳細リンクは残す。
- 詳細リンクは現状どおり請求ドラフト詳細画面への遷移でよい。

## BE 指示

### 1. 既存 `/api/v1/invoices/draft-list` を一覧用途に合わせて拡張

現状の `draft-list` では以下が返っている。

- `invoice_id`
- `invoice_item_id`
- `customer_name`
- `billable_qty`
- `sales_unit_price`
- `unit_cost_basis`
- `line_amount`
- `gross_margin_pct`
- ほか

一覧ヘッダーに必要なため、少なくとも以下を追加して返すこと。

1. `invoice_no`
2. `invoice_date`
3. `delivery_date`
4. `status`

備考:

- `invoice_id` は内部ID、`invoice_no` は画面表示用番号として両方保持してよい。
- 現在 `draft-list` は `Invoice.status == draft` で絞っているが、画面要件上ステータス列を表示するので、そのまま `draft` 固定表示でも問題ない。
- 将来的に finalized/sent も同画面で扱う可能性があるなら、絞り込み条件の扱いは実装者判断で拡張可能。

### 2. 粗利% の計算は既存ロジックを流用

- 既存の `_draft_item_metrics(item)` を流用する。
- 粗利% は `gross_margin_pct` をそのまま返す。
- 算出不可時は `gross_margin_unavailable=true` を返し、FE では `-` 表示にする。

### 3. 明細行更新 API は既存 `PATCH /api/v1/invoices/{invoice_id}/items/{invoice_item_id}` を利用継続

現状この API で以下は更新可能。

- `billable_qty`
- `sales_unit_price`

今回の要件では一覧上に以下が必要。

- 請求単価入力欄
- 請求数量

そのため BE 側は原則追加API不要。既存 PATCH をそのまま利用する前提でよい。

ただし以下を確認すること。

1. 更新後レスポンスまたは再取得で `gross_margin_pct` が最新値として見えること
2. `sales_unit_price` 更新時に `line_amount` が再計算されること
3. `billable_qty` 更新時に `line_amount` が再計算されること
4. 請求書ヘッダの `subtotal/tax_total/grand_total` が再計算されること

### 4. 必要なら PATCH レスポンスに最新粗利% を含める

現状の明細更新後画面反映を軽くしたい場合は、PATCH のレスポンスに以下を確実に含めること。

- `gross_margin_pct`
- `gross_margin_unavailable`
- `line_amount`

すでに `InvoiceItemResponse` に項目はあるため、戻り値整合性を確認すること。

## FE 指示

### 1. 一覧画面のデータ取得元を `listInvoiceSummaries()` から `listInvoiceDraftListRows()` ベースへ変更

現状 `InvoiceDraftPage.tsx` は請求書単位サマリを読んでいる。
今回の要件では明細行表示が必要なため、行データは `listInvoiceDraftListRows()` を使うこと。

必要なら `invoiceService.ts` 側で `ApiInvoiceDraftListRow` と `InvoiceDraftListRow` を拡張すること。

### 2. 一覧テーブルを明細行ベースに変更

テーブル列は以下の順で表示する。

1. チェックボックス
2. 詳細
3. 請求ヘッダー番号
4. 取引先名
5. 請求日
6. 納品日
7. ステータス
8. 仕入単価
9. 請求単価
10. 請求数量
11. 請求金額
12. 粗利%

表示ルール:

- 請求ヘッダー番号: `invoice_no` を表示
- 仕入単価: `unit_cost_basis`
- 請求単価: 編集可能 input
- 請求数量: 要件上は表示必須。運用上修正が必要なら編集可能 input にしてよい
- 請求金額: `line_amount`
- 粗利%: `gross_margin_pct`
- 算出不可時: `-` 表示。必要なら tooltip/補足で `auto_price_error` を見せる

### 3. チェックボックスの挙動

- 現在は請求書単位で選択しているが、明細行ベース一覧になるため、見た目上は請求書IDが重複する。
- 一括発行は請求ヘッダ単位なので、選択状態の内部管理は `invoiceId` 単位を維持すること。
- 同一 `invoiceId` の行を1つ選んだら、その請求ヘッダ全体を選択扱いにする。
- ヘッダの全選択も「表示中の請求ヘッダを全選択」として扱う。

### 4. 詳細リンクは維持

- 詳細リンクは現状どおり `/invoices/drafts/:invoiceId` に遷移
- 同一請求ヘッダの各明細行から同じ詳細へ飛ぶ仕様でよい

### 5. 請求単価入力時の更新

- `salesUnitPrice` を編集したら既存 PATCH API を呼ぶ
- 更新成功後は該当行の `salesUnitPrice` `lineAmount` `grossMarginPct` を更新
- 必要ならその請求ヘッダ配下の他行ではなく、当該行のみ即時更新でよい
- 一括再取得でもよいが、操作感が重くならない方を優先

### 6. 請求数量の扱い

要件文ではヘッダに「請求数量」があるため表示は必須。

運用判断:

- 数量も一覧上で編集するなら `billableQty` を PATCH
- 数量は表示のみで、編集は詳細画面に残す判断でもよい

ただし今回の依頼文は「請求単価入力欄」を明示しており、「請求数量入力欄」は明示されていない。
そのため最小実装は以下でよい。

- 請求単価: 入力欄
- 請求数量: 表示のみ

### 7. 粗利% 表示

- `gross_margin_pct` を小数点桁数を決めて `%` 付き表示
- 例: `12.3%`
- 算出不可時は `-`

## 推奨実装方針

最小差分で進めるなら以下。

1. BE で `draft-list` に `invoice_no / invoice_date / delivery_date / status` を追加
2. FE の `InvoiceDraftPage.tsx` を `InvoiceDraftListRow[]` ベースに差し替え
3. 請求単価のみ一覧編集可能にする
4. 選択状態は `invoiceId` 単位のまま維持
5. 一括発行処理は既存 `finalizeInvoiceDraftsBatch()` を流用

## 受け入れ条件

1. 請求ドラフト一覧で請求明細行が1行ずつ表示される
2. 指定ヘッダーが表示される
3. 仕入単価が見える
4. 請求単価が入力欄で編集できる
5. 請求単価更新後、請求金額と粗利%が更新される
6. チェックボックスと詳細リンクが残っている
7. 一括発行は従来どおり請求ヘッダ単位で動く
8. 詳細画面への遷移は壊れない

## 注意点

- 一覧を明細行ベースにすると同一請求ヘッダが複数行に出るため、選択UIの意味を崩さないこと
- 仕入単価未設定時の表示を崩さないこと
- 一覧編集後に請求書ヘッダ合計と詳細画面内容に不整合が出ないこと
