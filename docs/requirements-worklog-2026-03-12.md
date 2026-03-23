# 要件定義 作業ログ（2026-03-12）

対象プロジェクト: `order_system`
作成者: OpenClawBot

---

## 目的
本日の要件定義に関する、KojiのインプットとBotのアウトプットを時系列で記録する。

---

## 時系列ログ（Input / Output）

### 1) 用語確認
**Input（Koji）**
- `unit_price_uom_count` と `unit_price_uom_kg` の意味を再確認したい。

**Output（Bot）**
- `unit_price_uom_count`: 数量単位（count）あたり販売単価。
- `unit_price_uom_kg`: kg単位あたり販売単価。
- 計算の使い分け（`uom_count` / `uom_kg`）を説明。

---

### 2) API基本用語確認
**Input（Koji）**
- Response fields / Endpoint の意味を確認。

**Output（Bot）**
- Request fields = 入力、Response fields = API返却値。
- Endpoint = APIの呼び出し先（例: `POST /api/orders`）。

---

### 3) I/Oマトリクス整備（ODS）
**Input（Koji）**
- `docs/IO_from_order_to_invoice.ods` を作成。
- Order→Allocation→Split→Purchase Result→Invoiceまで、入力/出力/継承項目を整理したい。

**Output（Bot）**
- ODSを実データで埋め、各段階の項目を整理。
- 継承元（Inherited From）を含む形で構造化。
- Git反映:
  - `e22bfef` Complete IO spreadsheet from order to invoice with inheritance mapping

---

### 4) 仕様フォーマット標準化
**Input（Koji）**
- この形式が標準的か確認。
- さらに3項目追加したい。

**Output（Bot）**
- 実務上標準的なData Dictionary形式であると回答。
- 以下3列をODSに追加:
  - Allowed values
  - Validation rule
  - System of record
- Git反映:
  - `9763a16` Add allowed values, validation rule, and source-of-record columns to IO spreadsheet

---

### 5) Auto Allocationの前段I/O明確化
**Input（Koji）**
- Allocation Overrideの前に、Auto Allocationの入力/出力項目をマトリクスへ追加したい。

**Output（Bot）**
- ODSにAuto Allocation行を追加:
  - 入力: `default_supplier_id`, `order_item_id`
  - 出力: `suggested_*`, 初期`final_*`, `line_status`更新
- Git反映:
  - `5899d04` Add explicit Auto Allocation input/output rows before override in IO matrix

---

### 6) Invoice内部管理項目（販売単価・粗利）追加
**Input（Koji）**
- Invoiceに販売単価項目を追加したい。
- Invoiceに粗利項目を追加したい。
- 粗利式: `(販売単価 - 原価) / 原価`
- split仕入れ時は原価を加重平均。
- 粗利はInvoice印刷に含めない。

**Output（Bot）**
- docs更新:
  - `docs/invoice-rules-draft.md`
  - `docs/report-and-api-io-definition-draft.md`
  - `docs/db-dual-uom-draft.md`
- 仕様反映:
  - `sales_unit_price`
  - `unit_cost_basis`（split時 加重平均）
  - `gross_margin_rate`（内部項目、PDF非表示）
- Git反映:
  - `5df0716` Add sales unit price and gross margin rules to invoice specs

---

### 7) ODSにも販売単価・粗利を反映
**Input（Koji）**
- 上記をマトリクスODSにも反映したい。

**Output（Bot）**
- ODS更新:
  - `sales_unit_price`
  - `unit_cost_basis`
  - `gross_margin_rate`
  - 印刷非表示ルール
- Git反映:
  - `f6066e4` Update IO matrix ODS with sales price and gross margin fields

---

## 本日の決定事項（要約）
1. Invoice内部管理に「販売単価」「粗利」を保持する。
2. 粗利は `(販売単価 - 原価) / 原価`。
3. split仕入れ時の原価は加重平均。
4. 粗利は顧客向け請求書（PDF）に出さない。
5. I/Oマトリクスは「Allowed values / Validation rule / System of record」を含む標準形式で運用する。

---

## 参照コミット（本日関連）
- `e22bfef`
- `9763a16`
- `5899d04`
- `5df0716`
- `f6066e4`

---

## 次アクション（提案）
- このログを基に、UATチェックリストへ「粗利検証ケース」を追加。
- 実装側（API/DB）に `sales_unit_price`, `unit_cost_basis`, `gross_margin_rate` の受け渡し定義を反映。
