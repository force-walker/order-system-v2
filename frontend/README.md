# Frontend MVP Guide

## 起動（推奨）

リポジトリルートで以下を実行:

```bash
./start-dev.sh
```

停止:

```bash
./stop-dev.sh
# 必要なら node_modules も削除
./stop-dev.sh --clean-node-modules
```

## 手動起動（frontendのみ）

```bash
cd frontend
npm ci
npm run dev
```

## テスト・ビルド

```bash
cd frontend
npm run test
npm run build
```

## ブランチ表示ルール

`frontend/.env.development` の `VITE_APP_BRANCH` を、
作業ブランチ名に合わせて更新する。

例:

```env
VITE_APP_BRANCH=feat/frontend-pr17-mvp-finalization
```

## MVP 主要フロー確認

1. 注文作成
2. 注文一覧（検索/状態フィルタ/並び順）
3. 注文編集（ヘッダー更新・明細追加/更新/削除）
4. 顧客作成・編集
5. 商品作成・編集

保存成功時は一覧ページでトースト表示される。
