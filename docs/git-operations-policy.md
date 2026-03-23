# Git運用方針（Branching Strategy）

Date: 2026-03-24
Status: Adopted (v2)

## 1) ブランチ構成

- `main`
  - 公式の統合ブランチ
  - 直接コミット禁止（PR経由のみ）
- `feature/*`
  - 機能開発用（`main` 起点）
- `fix/*`
  - バグ修正用（`main` 起点）
- `chore/*`
  - CI/依存更新/保守作業用（`main` 起点）
- `hotfix/*`
  - 緊急修正用（`main` 起点、例外運用）

> `rebuild/*` のような長寿命統合ブランチは採用しない。

## 2) 通常開発フロー

1. `main` から作業ブランチを作成（`feature/*` / `fix/*` / `chore/*`）
2. 変更を小さくまとめて push
3. `main` 宛にPR作成
4. CI必須チェック通過（lint/test）
5. 最低1レビュー承認
6. squash merge

## 3) 保護ルール（main）

- PR必須
- Required approvals: 1
- Dismiss stale approvals: ON
- Required status checks: `backend-lint`, `backend-schema`, `backend-test`
- マージ方式: squash 推奨

## 4) staging の位置づけ

- `staging` は**ブランチではなく環境（Environment）**として扱う
- 当面（MVP非公開期間）は `local + CI` 運用
- 公開段階で `staging` / `production` をEnvironmentとして有効化し、secretsを分離

## 5) 例外運用（緊急障害）

- 本番障害時のみ `hotfix/*` を許可
- 事後に必ずPRで履歴を整備し、通常運用に戻す

## 6) 補足ルール

- PRは小さく（1テーマ1PR）
- 長寿命ブランチを避ける
- 破壊的変更は事前にArchitecture/Infraで合意
