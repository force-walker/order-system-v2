# 権限変更ポリシー（MVP→将来拡張）

Updated: 2026-03-16

## 目的
業務運用の変化に合わせて、権限モデル（RBAC）を安全に変更できるようにする。

---

## 現行方針（MVP）

- supplierの入力は **発注者の入力補助** と位置づける
- supplierは担当行に対して入力可能（例: `final_unit_cost`）
- **最終validation責任は発注者（buyer）** が持つ
- 請求確定前に buyer/admin のレビューを必須とする

---

## 権限変更の原則

1. **可逆性**
- 変更はいつでも戻せる構成にする（設定で切替）

2. **監査可能性**
- 誰がいつ何を変更したか（権限定義含む）を記録する

3. **段階的適用**
- 一括変更ではなく、対象ロール/機能を段階的に拡張

4. **業務責任と整合**
- 権限は実運用上の責任者に合わせる

---

## 推奨アーキテクチャ

## A) 権限定義の設定化
- コード固定ではなく設定ファイル/DBテーブルでロール権限を管理
- 例:
  - `role_permissions` テーブル
  - `user_permission_overrides` テーブル（ユーザー個別 Allow/Deny）
  - `feature_flags`（`supplier_final_cost_mode` など）

優先順位（MVP推奨）:
1. `user_explicit_deny`
2. `user_explicit_allow`
3. `group_permission`
4. default deny

## B) 2段階確定モデル
- supplier入力 → buyer検証 → invoice確定
- 検証フラグ例:
  - `is_verified_by_buyer` (bool)
  - `verified_by`, `verified_at`

## C) スコープ制御
- supplier/customerは自分の対象データのみ
- スコープ外アクセスは403で拒否

## D) 常時監査
- override, cost更新, 権限変更はすべて監査ログ対象

---

## 変更パターン（将来）

### パターン1: supplierは提案のみ
- `final_unit_cost` は提案値として保存
- buyerのみ確定可能

### パターン2: supplierが確定まで可能
- supplierが確定値更新可能
- ただし高リスク条件（価格乖離など）はbuyer承認必須

### パターン3: 閾値ベース承認
- 価格乖離 <= X%: supplier確定可
- 価格乖離 > X%: buyer/admin承認必須

---

## 権限変更手順（運用）

1. 変更要求起票（背景、対象、影響）
2. 影響分析（業務・請求・監査）
3. ステージングで検証（UAT実施）
4. 承認（業務責任者 + システム管理者）
5. 本番反映（低負荷時間帯）
6. 反映後モニタリング（1〜2週間）

---

## 最低限の承認基準

- 誤請求リスク増加がない
- 監査証跡が維持される
- rollback手順がある
- 運用責任者の合意がある

---

## 現在の結論（2026-03-16）

- 現時点は「supplier入力補助 / buyer最終validation」で運用
- 権限モデルは **グループベース + ユーザー個別例外** の併用を前提とする
- cancel詳細運用は `docs/permission_matrix_cancel.csv` を基準に管理する
- 将来変更は想定済みとし、設定切替可能な設計を優先する
