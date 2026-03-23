# Git運用方針（Branching Strategy）

Date: 2026-03-22
Status: Adopted

## 1) ブランチ構成

- `main`
  - 本番基準ブランチ
  - 直接コミット禁止
- `rebuild/order-system`
  - 再構築フェーズの統合ブランチ
- `feature/*`
  - 機能開発用（`rebuild/order-system` 起点）
- `fix/*`
  - バグ修正用（`rebuild/order-system` 起点）
- `chore/*`
  - CI/依存更新/保守作業用（`rebuild/order-system` 起点）

## 2) 通常開発フロー

1. `feature/*` / `fix/*` / `chore/*` を作成
2. `rebuild/order-system` 宛にPR
3. CI（lint/test/build）通過
4. 最低1レビュー
5. squash merge 推奨

## 3) main 統合条件

`rebuild/order-system` から `main` への統合は、以下確認後に実施:

- E2E確認
- 監視項目確認
- DB移行手順 + ロールバック手順確定
- 統合後タグ付け: `vX.Y.Z`

## 4) 例外運用（緊急障害）

- 本番障害時のみ `hotfix/*` を `main` 起点で許可
- 修正は **必ず `rebuild/order-system` にも逆マージ**（差分ドリフト防止）

## 5) 補足ルール

- PRは小さく（1テーマ1PR）
- 長寿命ブランチを避ける
- 破壊的変更は事前にArchitecture/Infraで合意

