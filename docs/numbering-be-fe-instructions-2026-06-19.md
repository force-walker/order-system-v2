# 番号体系見直し BE/FE 指示

作成日: 2026-06-19
参照元: `docs/numbering-spec-2026-06-19.md`

## 1. 目的

- 内部IDと表示番号を分離する
- 注文/納品/請求を横断する共通案件番号を導入する
- 請求ドラフト番号と正式請求書番号を分離する
- 採番責務を FE から BE に寄せる

## 2. BE 指示

### 2.1 主キー方針

- 今後の対象エンティティは UUID 主キー前提で設計する
- 少なくとも以下を移行対象候補として整理する
  - orders
  - order_items
  - invoices
  - invoice_items
  - delivery headers/items を新設する場合は同様

補足:

- 既存の数値IDを即時全面置換するか、UUID列追加後に段階移行するかは実装計画で決める
- MVPではまず UUID 追加 + API応答に表示番号を出す段階移行でもよい

### 2.2 表示番号カラム追加案

- `orders.tracking_no`
- `orders.order_no`
- `order_items.order_line_no`
- `invoices.invoice_draft_no`
- `invoices.official_invoice_no`
- `invoice_items.invoice_line_no`

納品を独立エンティティ化する際:

- `deliveries.delivery_no`
- `delivery_items.delivery_line_no`

### 2.3 採番ロジック

- `tracking_no`: 注文作成時に `YYYYMMDD-XXXXX`
- `order_no`: `ORD-{tracking_no}`
- `order_line_no`: `ODL-{XXXXX}-{ZZZZ}`
- `invoice_draft_no`: 請求ドラフト作成時に `IVD-{YYYYMMDD}-{XXXXX}-{SS}`
- `invoice_line_no`: `IVL-{XXXXX}-{SS}-{ZZZZ}`
- `official_invoice_no`: 請求確定時に `INV/{YYYY}/{NNNNN}`

### 2.4 重要ルール

- FE で `invoice_no` を組み立てない
- 現在の `DRAFT-{markerId}-{Date.now()}` 方式は廃止する
- 正式請求書番号の採番は請求確定時のみ
- `tracking_no` は欠番許容、再利用禁止
- `official_invoice_no` は欠番管理対象

### 2.5 競合・整合性

- 正式請求書番号 `INV/{YYYY}/{NNNNN}` は年ごとの排他採番が必要
- DBトランザクション内で採番する
- 連番テーブル or system_settings系の採番管理テーブル新設を推奨

### 2.6 API変更方針

注文系API:

- `id` に加えて `tracking_no`, `order_no` を返す
- 明細に `order_line_no` を返す

請求系API:

- `invoice_draft_no`
- `official_invoice_no`
- 必要に応じて `tracking_no`
- 明細に `invoice_line_no`

請求ドラフト作成API:

- FE から `invoice_no` を受けない設計に変更する
- BE がドラフト番号を採番して返す

## 3. FE 指示

### 3.1 表示方針

- 一覧・詳細・帳票プレビューでは UUID ではなく表示番号を使う
- 内部操作やAPI更新キーには UUID/内部ID を使う

### 3.2 注文画面

- ヘッダー表示は `order_no`
- 明細表示は `order_line_no`
- 既存で注文番号を明細番号代わりに見せている箇所があれば解消する

### 3.3 請求画面

- ドラフト中は `invoice_draft_no` を表示
- 確定後は `official_invoice_no` を主表示にする
- 必要ならサブ表示で `invoice_draft_no` を残す

### 3.4 ドラフト作成フロー

- 現在の FE 採番を廃止する
- BE レスポンスのドラフト番号をそのまま表示に使う

### 3.5 画面文言

- `DRAFT-...` の露出をなくす
- 正式請求書番号とドラフト番号のラベルを分ける
  - 例: `請求ドラフト番号`
  - 例: `正式請求書番号`

## 4. 検討事項

### 4.1 1請求に複数注文をまとめるか

- まとめる想定があるなら、請求ヘッダーに単一 `tracking_no` を持たせるだけでは不足する
- MVPでは `1請求 = 1 tracking_no` に寄せるのが安全

### 4.2 納品独立モデルの導入時期

- 納品ヘッダー/明細の実体化前に番号仕様だけ先に合意しておく
- 実装は納品モデル導入時に行う

## 5. 推奨実装順

1. 番号仕様を合意
2. 請求ドラフトの FE 採番廃止
3. BE で `invoice_draft_no` 採番導入
4. FE を新番号表示へ切替
5. 正式請求書番号 `INV/YYYY/NNNNN` を請求確定時採番にする
6. 注文/注文明細の表示番号整理
7. UUID化を段階移行

## 6. 受け入れ条件

1. FE で表示番号と内部IDの役割が分離されている
2. 請求ドラフト番号は BE 採番になっている
3. `DRAFT-...` 形式は廃止されている
4. 正式請求書番号は確定時のみ `INV/YYYY/NNNNN` で採番される
5. 注文明細・請求明細に専用表示番号がある
6. 共通 `tracking_no` で注文/納品/請求の関係が追える
