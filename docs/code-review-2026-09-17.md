# コードレビュー・動作を維持するリファクタリング

> 後続対応: この文書で指摘した認証、UUID、起動順序の問題は、その後の実装で修正済みです。
> 現在の仕様は `authentication.md`、`uuid-frontend-repair.md`、`remote-development.md` を参照してください。

対象: `191a461` と既存のリモート開発設定を含む作業ツリー。
ブランチ: `codex/remote-development`。

## 今回の確認範囲

注文・請求・配送APIの注文検索、フロントエンド7サービスの認証付き通信、
APIと画面のID型の整合性、認証実装、開発環境の起動・停止処理を重点確認した。
全画面のE2Eやすべての業務計算を網羅した監査ではない。
既存の未コミット変更を保持し、DB・マイグレーション・環境設定は変更していない。
`backend/.env` は表示・コピーしていない。

## 発見事項（動作が変わる修正は未実施）

### P1: UUIDと数値IDの不整合

- `backend/app/schemas/order.py:62` と `backend/app/schemas/invoice.py:80` は `id: str` を返す。
- `frontend/src/generated/openapi.ts` の OrderResponse / InvoiceResponse はまだ `id: number`。
- `frontend/src/features/orders/pages/OrderEditPage.tsx:59` はURLのIDを `Number(orderId)` に変換する。
  UUID文字列はNaNになり、同ファイルのIDチェックで「不正な注文IDです」になる。
- OrderItemDetailPage、InvoiceDetailPage、InvoiceDraftDetailPage にも数値変換がある。

型チェックだけでは検出できない、生成型と実APIの乖離がある。
別の不具合修正として、実APIからの型生成と画面・サービス・キャッシュの文字列ID対応を揃え、
UUIDの詳細表示・編集・請求確定をE2Eで検証する必要がある。
今回はその挙動を変更していない。

### P1: 認証・権限管理は開発用のまま

- `backend/app/api/routes_auth.py:15` のloginは、利用者の本人確認なしで指定されたuser_id/roleのトークンを発行する。
- 注文・配送などのAPIには `get_auth_context` / `require_roles` の依存が付いていない。
- `docs/architecture/05-authn-authz.md` の本番向け方針と現在の実装には差がある。

現在は信頼できるTailscale内の開発利用が前提。
一般公開・業務利用に進む際は、認証と権限の実装を別途扱う必要がある。
今回の共通化はログイン方式やアクセス可能範囲を変更しない。

### P2: 再起動時のマイグレーションがサービス停止より先

`start-dev.sh:36` の Alembic 実行は、API/画面サービスを停止する処理より先にある。
未適用のスキーマ変更がある状態で稼働中サービスを再起動すると、旧処理が動いたままDB更新が進む。
現時点で再現した障害ではないが、今後の互換性のないスキーマ変更では問題になり得る。
サービス停止・更新失敗時の復旧方針を含めて起動手順を改善する対象として残す。
今回は起動順序を変更していない。

## 実施した整理

### バックエンド

3箇所の注文検索を `backend/app/api/order_lookup.py` に集約。
各ルートの既存名をimport aliasで維持した。

- 主キーの一致を優先する。
- 数字だけの識別子はlegacy_idへフォールバックする。
- 先頭ゼロ付きの数字、負数、空白付き文字列の扱いを維持する。
- 404のステータス、code、messageを維持する。
- APIの引数・レスポンス・URLは変更しない。

### フロントエンド

注文、請求、仕入、割当、帳票、仕入先、環境設定の7サービスから認証付き通信の重複を除き、
`frontend/src/shared/authenticatedApiClient.ts` に集約。

- 開発用ログインの環境変数と既定値を維持する。
- localStorageのキーとトークン保存・再利用を維持する。
- 401時はトークンを削除し、そのリクエストを自動再送しない。
- 通信失敗時には保存トークンを保持する。
- エラー変換は従来の `apiJson` / `parseApiErrorPayload` を利用する。
- 同時ログインの集約、自動refresh、UI、業務リクエストや計算式は変更しない。

## 検証

- 既存バックエンド178件に、検索互換性の27件を追加。共通化前後で205件すべて成功。
- 既存フロントエンド6件に、7サービス×5パターンの認証通信テスト35件を追加。
  フロントエンド共通化前後で41件すべて成功。
- `npm run typecheck` / `npm run build` 成功。
- `git diff --check` 成功。
- 変更前後のOpenAPIをキー順で正規化したSHA-256が一致:
  `bba90ffd6f70bdb540b86cff2037340bfc88c51355ce67a5bf776de6bf6c61de`。
- バックエンドテストにはメモリ内SQLiteを使用。稼働中のPostgreSQLには接続しない。
  制限環境ではTestClientのスレッド待機で停止したため、許可を受けて制限外で実行した。

既存のReportLab非推奨警告とViteの大きなJSバンドル警告は残っている。
今回、実端末からのE2EとPostgreSQL固有の動作検証は行っていない。
