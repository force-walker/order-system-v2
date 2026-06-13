# 取引先 Import 機能 作業指示

## 目的

商品マスタで提供している Import 機能と同様に、取引先マスタでも一括 Import を行えるようにする。

今回は対象をマスタ系に限定し、伝票系の Import は含めない。

本指示では、取引先を以下 2 系統に分けて実装対象とする。

- 顧客 (`customers`)
- 仕入先 (`suppliers`)

## 前提

- 既存の商品の Import 実装を基準にする
  - Backend: `backend/app/api/routes_products.py` の `/api/v1/products/import-upsert`
  - Frontend: `frontend/src/features/products/pages/ProductImportPage.tsx`
- 取引先 Import も、まずは `JSON` / `CSV` / `XLSX` の取り込みに対応する
- 既存データの更新と新規作成を同一 API で扱う `upsert` 方式とする
- 削除は Import で行わない

## スコープ

今回のスコープは「取引先マスタの一括登録・更新」のみとする。

対象外:

- 受注
- 発注
- 出荷
- 請求
- その他の伝票系 Import

### 顧客 Import

- 新規作成
- 既存更新
- エラー行の返却
- 事前バリデーション

### 仕入先 Import

- 新規作成
- 既存更新
- エラー行の返却
- 事前バリデーション

## Import の基本方針

- 更新キーは `import_key` を追加して利用する
- `import_key` が一致する既存レコードがあれば update、なければ create
- `import_key` 未指定行は create のみ許可
- create 時の必須項目が足りない場合は、その行だけエラーにして継続
- 1 行単位で savepoint を張り、他の正常行は取り込み継続
- 結果は `total / created / updated / skipped / failed / errors[]` を返す

## 取り込み対象フィールド

最初の実装では、既存スキーマにある項目だけを対象にする。

### 顧客

- `import_key`
- `customer_code` は入力不可
  - create 時は自動採番
  - update 時も変更不可
- `region`
- `name`
- `active`

### 仕入先

- `import_key`
- `supplier_code` は入力不可
  - create 時は自動採番
  - update 時も変更不可
- `name`
- `active`

## Backend 作業指示

### 1. DB / Model 整備

- `Customer` と `Supplier` に `import_key` カラムを追加
- 制約案
  - nullable 許可
  - 一意制約あり
  - 長さは products と揃えて `128` 以内
- Alembic migration を追加

### 2. Schema 追加

- `backend/app/schemas/customer.py`
  - `CustomerImportItem`
  - `CustomerImportRequest`
  - `CustomerImportError`
  - `CustomerImportResult`
- `backend/app/schemas/supplier.py`
  - `SupplierImportItem`
  - `SupplierImportRequest`
  - `SupplierImportError`
  - `SupplierImportResult`

ルール:

- `model_config = {"extra": "forbid"}`
- `items` は 1..2000 件
- `active` は省略時 `None` を許可
- 文字列の空欄は `None` 扱いで受ける前提

### 3. API 追加

- `backend/app/api/routes_customers.py`
  - `POST /api/v1/customers/import-upsert`
- `backend/app/api/routes_suppliers.py`
  - `POST /api/v1/suppliers/import-upsert`

実装方針:

- products の import-upsert をベースに流用
- 1 行ずつ `model_validate`
- payload 内 `import_key` 重複を検出
- create 時:
  - 顧客は `name` 必須
  - 仕入先は `name` 必須
- update 時:
  - `None` は原則「更新しない」
  - 値が変わらない場合は `skipped`
- create 時のコード採番:
  - 顧客: `CUST-`
  - 仕入先: `SUP-`
- audit log を create / update ごとに記録
- `IntegrityError` は既存ユーティリティに合わせて code/message 化

### 4. エラーコード方針

最低限、products と同等の以下を揃えること。

- `ITEM_VALIDATION_ERROR`
- `DUPLICATE_IMPORT_KEY_IN_PAYLOAD`
- `REQUIRED_FIELDS_MISSING`
- `DB_ERROR`

必要に応じて追加:

- `CUSTOMER_IMPORT_KEY_ALREADY_EXISTS`
- `SUPPLIER_IMPORT_KEY_ALREADY_EXISTS`

ただし、可能なら DB の一意制約違反を共通エラーマッピングで吸収する。

### 5. OpenAPI / テスト

- OpenAPI contract test を更新
- API テストを追加

顧客テスト観点:

- create 成功
- update 成功
- `import_key` 重複行エラー
- create 必須不足
- 空更新で `skipped`
- 一部失敗でも他行継続

仕入先テスト観点:

- create 成功
- update 成功
- `import_key` 重複行エラー
- create 必須不足
- 空更新で `skipped`
- 一部失敗でも他行継続

## Frontend 作業指示

### 1. Import ページ追加

商品 Import ページをベースに、以下 2 画面を作成する。

- `frontend/src/features/customers/pages/CustomerImportPage.tsx`
- `frontend/src/features/suppliers/pages/SupplierImportPage.tsx`

対応内容:

- JSON 貼り付け
- CSV 読み込み
- XLSX 読み込み
- 送信前バリデーション
- 実行結果表示
- エラー行一覧表示

### 2. Service 追加

- `frontend/src/features/customers/services/customersService.ts`
  - `importCustomersUpsert`
- `frontend/src/features/suppliers/services/suppliersService.ts`
  - `importSuppliersUpsert`

API:

- `POST /api/v1/customers/import-upsert`
- `POST /api/v1/suppliers/import-upsert`

### 3. 型追加

- 顧客 import request / result 型
- 仕入先 import request / result 型
- products 側と同じ `total / created / updated / skipped / failed / errors` を揃える

### 4. 画面導線

- 顧客一覧に `Import` 導線を追加
  - 例: `/customers/import`
- 仕入先一覧に `Import` 導線を追加
  - 例: `/suppliers/import`
- `App.tsx` に route 追加

### 5. Frontend 事前バリデーション

商品 Import と同じく、送信前に最低限の整形を行う。

顧客:

- 空文字を `null`
- `active` は boolean 解釈
- `created_at` / `updated_at` は送信前に破棄

仕入先:

- 空文字を `null`
- `active` は boolean 解釈
- `created_at` / `updated_at` は送信前に破棄

注意:

- `customer_code` / `supplier_code` は入力されていても送信しない
- `id` も送信しない

### 6. UI 表示要件

- サンプル JSON を画面上に表示
- CSV ヘッダ例を画面に明記
- 取り込み件数サマリを表示
- エラーは最大 100 件程度まで一覧表示
- products と同じ文言トーンに揃える

## CSV ヘッダ案

### 顧客

```csv
import_key,region,name,active
cust-001,kanto,テスト顧客,true
```

### 仕入先

```csv
import_key,name,active
sup-001,テスト仕入先,true
```

## 受け入れ条件

- 顧客一覧から Import 画面へ遷移できる
- 仕入先一覧から Import 画面へ遷移できる
- CSV / XLSX / JSON のいずれでも取り込みできる
- create / update / skipped / failed が正しく集計される
- 不正行があっても正常行は継続取り込みできる
- backend / frontend のエラー表示が products と同程度に分かる
- OpenAPI とテストが更新されている

## 実装順の推奨

1. Backend: model + migration
2. Backend: schema + import API + tests
3. Frontend: service + import pages + routes
4. Frontend: list page への導線追加
5. E2E 手動確認

## 補足

- 今回の「取引先」は顧客と仕入先の両方を指す
- 今回はマスタ系のみを対象とし、伝票系 Import は別タスクで扱う
- 将来的に得意先/請求先/納品先や伝票系へ拡張する場合も、`import_key` ベースの upsert ルールを共通化すると再利用しやすい
