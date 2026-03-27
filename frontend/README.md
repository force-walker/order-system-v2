# Frontend Mockup (PR1 start)

## 実行方法

```bash
cd frontend
npm install
npm run dev
```

## モックアップ完了条件

- 注文作成 → 注文一覧 → 注文アイテム詳細 の遷移
- Loading / Empty / Error の状態確認

## PR分割（3〜5本）

### PR1: 土台 + ルーティング + 3画面骨格（このコミット）
- React + Vite + TS 初期化
- `/orders/new` `/orders` `/orders/:orderId/items/:itemId`
- 共通状態UI（Loading/Empty/Error）

### PR2: 注文作成フォームUI反映 + バリデーション
- UI案（OrderInput）への寄せ
- 入力エラーの改善
- 必須/形式チェック整理

### PR3: 注文一覧/アイテム詳細の表示改善
- テーブル列調整
- ステータス表示改善
- UI案（Invoice）とのトーン統一

### PR4: API接続の最小実装
- login→token保持
- `GET /orders`, `POST /orders` 接続
- モック/実API切替フラグ

### PR5: 仕上げ
- エラーハンドリング統一
- 最低限のコンポーネントテスト
- docsと進捗投稿更新
