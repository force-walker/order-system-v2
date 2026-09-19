# 登録・ログイン・ログアウト（2026-09-17）

## 実装前の確認結果

| 機能 | API | Frontend | 操作可能だったか | 既存テスト |
| --- | --- | --- | --- | --- |
| 新規登録 | なし | なし | 不可 | なし |
| ログイン | POST /api/v1/auth/login | Login画面なし。サービスが開発用のuser_id/roleで自動ログイン | 本人確認を伴うログインは不可 | 簡易login/refresh/me、入力検証 |
| ログアウト | POST /api/v1/auth/logout | ボタンなし | APIはokを返すだけでトークン失効なし | サーバー失効テストなし |

Userモデル・Protected Route・認証Context・メール送信/検証機構は存在しなかった。
Customerは顧客マスタで、認証ユーザーとの既存の関連はない。
`EMAIL_VERIFICATION_REQUIRED` の参照も既存の管理済みコードにはなかった。
`backend/.env` の内容は確認・表示・コピーしていない。

## 追加・変更

- auth_users / auth_sessions の2テーブルを新設。既存Customerや業務データは変更しない。
- 新規登録APIと画面。ユーザーIDは小文字に正規化、重複は409、パスワードは12〜128文字。
- 登録時のroleはサーバー側でorder_entry固定。role/customer_id/email_verified等の追加POSTフィールドは422。
- user_id/passwordでログインし、パスワード不一致・不明ユーザーは401。
- アプリの全業務ルーターにBearer認証を適用。healthは公開のまま。
- AuthProvider / ProtectedRoute、Login / Register、ヘッダーのログアウトを追加。
- ログアウト直後に画面と端末の認証状態を破棄し、サーバーでも当該セッションを失効。
- 戻る操作、別タブのstorageイベント、BFCache復帰時の認証再確認に対応。
- 認証変更時に注文等のメモリキャッシュを消し、旧ユーザーの処理中レスポンスを新ユーザーのキャッシュに入れない。
- 開発用自動ログインを削除。接続確認APIにも認証ヘッダーを付ける。
- 仕入保留の画面側実行者名は固定の開発ユーザーから、ログインユーザーへ変更。

## 認証方式と互換性

パスワードはsalt付きPBKDF2-HMAC-SHA256（600,000回）でハッシュ化し、平文保存しない。
access/refreshは暗号学的乱数のBearerトークン。DBにはSHA-256のハッシュのみ保存する。
JWTの自己完結型認証から、DBで失効を確認するサーバーセッション方式に変更した。
JWT署名用の既定値dev-secretには依存しない。

API URL、TokenResponseのaccess_token/refresh_token/token_type/expires_in、meのuser_id/roleを維持した。
ログイン入力だけは、安全性のためuser_id/roleからuser_id/passwordへ変更した。
旧開発用トークンではログインできない。旧方式にはUserレコードが存在せず、自動で既存顧客をUserに変換する処理もない。

既存の有効期限設定名JWT_ACCESS_TTL_SECONDS（既定3600秒）、JWT_REFRESH_TTL_SECONDS（既定1209600秒）は維持。
refresh成功時は旧セッションを失効し、両トークンをローテーションする。
logoutは既存のrefresh_tokenボディを受け付け、Bearerのみでのログアウトにも対応する。
現在のセッションだけを失効し、別PCなどの別セッションを一括失効しない。

フロントエンドはlocalStorageのosv2_auth_sessionにトークンを保存する。
保存値だけではログイン判定せず、/auth/meでサーバー確認する。
401時は認証情報を削除してLoginへ戻る。自動refreshやPOSTの自動再送は行わない。
HTTP Cookie認証は使わない。HTTP通信は既存のTailscale経路内限定で利用する。

## メール確認ポリシー

既存にメール確認フローがなかったため、メール送信・確認リンク機能は今回追加していない。
EMAIL_VERIFICATION_REQUIREDが未指定/falseなら通常登録・ログイン可能。
trueなら未確認Userのlogin/me/refresh等は403、登録は503 EMAIL_VERIFICATION_UNAVAILABLEで停止する。
POST値で確認済み状態を設定できない。メール確認必須の環境では、確認機構を整備するまで登録を許可しない。
起動スクリプトは明示された同環境変数をAPIサービスへ渡す。backend/.envを読み込む新規処理は追加していない。

## テストと稼働確認

- Backend全体: 225件成功（メモリ内SQLite）。
- focused: test_auth_api.py / test_auth_migration.py / test_openapi_contract_api.py、25件成功。
- Backendでは登録・重複・不正資格情報・権限指定拒否・匿名API拒否・logout後のaccess/refresh拒否・別セッション維持・refresh再利用拒否・期限切れ・無効User・メール確認ゲートを確認。
- マイグレーションのテストでは既存Customerが維持され、自動生成Userがないことを確認。
- 従来の業務テストはconftestの明示した既存モジュールに限り実DBセッション付きで実行する。認証を迂回する本番コードやget_auth_contextの差し替えは導入していない。
- Frontend: 49件成功。うち画面フロー8件、7サービスの通信35件、既存エラー処理6件。
- npm run typecheck / npm run test / npm run build / npm run gen:types:check 成功。
- git diff --check / bash -n start-dev.sh 成功。
- 実環境はDBバックアップ後に2026091701を適用。既存顧客や既存業務レコードを変更しない追加テーブルのみ。
- ホストのブラウザでTailscale用URLの / → /login とRegister画面を確認。
- 実環境の匿名products APIは401、healthは200。
- 実環境のユーザー作成はしていない。登録・ログイン・ログアウトの操作テストは隔離したテスト環境で実施。
- 外出先の物理端末での操作と、PostgreSQLでの同時refresh競合の負荷テストは未実施。

既存のReportLab非推奨警告、Viteの大きなJSバンドル警告、テスト時のReact Router将来仕様警告は残る。

## 手動確認・別PCからの利用手順

1. ホストで ./start-dev.sh を起動し、電源・ネット接続・Tailscaleを維持する。
2. 別PCで、自分のTailscaleアカウントを接続し、ホスト共有招待を承認する。
3. http://100.115.155.118:5173/ を開く。未ログインならLogin画面になる。
4. 「初めての方：新規登録」からユーザーID、パスワード、確認用パスワードを入力する。
5. 登録後にLogin画面へ戻るので、登録した資格情報でログインする。
6. アプリ画面のヘッダーにユーザーIDと「ログアウト」が表示される。
7. ログアウト後、ブラウザの戻る・/orders/newへの直接入力・再読込でLoginに戻ることを確認する。
8. 同じブラウザの別タブでもログアウトが反映されることを確認する。

アプリのユーザーIDとTailscaleアカウントは別。パスワード・トークンをチャットへ貼り付けない。

## 今回の変更ファイル

Backend:
- app/models/auth.py
- app/core/auth.py
- app/schemas/auth.py
- app/api/routes_auth.py
- app/main.py
- alembic/env.py
- alembic/versions/2026091701_add_auth_users_sessions.py
- tests/test_auth_api.py
- tests/test_auth_migration.py
- tests/conftest.py

Frontend:
- src/features/auth/AuthContext.tsx / AuthPage.tsx / LogoutButton.tsx / AuthFlow.test.tsx
- src/shared/authSession.ts / authenticatedApiClient.ts / authServices.test.ts / error.ts
- src/app/App.tsx / AppLayout.tsx
- src/features/orders/pages/OrderCreatePage.tsx
- src/features/orders/services/ordersService.ts / purchaseService.ts
- src/generated/openapi.ts
- vite.config.ts
- package.json / package-lock.json（画面テスト用依存）

その他:
- docs/openapi-mvp-skeleton-draft.yaml（認証部分のみ更新）
- docs/authentication.md / remote-development.md / remote-user-guide.md
- HANDOFF.md
- start-dev.sh（認証ポリシー環境変数の引継ぎ）

前回までのリファクタリング・Tailscale設定等の未コミット差分も作業ツリーに残っている。
今回それらを戻していない。今回の修正と既存差分を区別して確認済み。コミットは未実施。

## 残るリスク・未実装

- 自己登録できるTailscale内の利用者はorder_entryとして業務データにアクセスできる。登録承認制・顧客別のデータ分離は未実装。
- 既存の細粒度RBACは一部APIのみ。全業務操作の役割別制限・監査実行者のサーバー強制は別途整備が必要。
- 管理者は自動生成しない。ユーザー管理画面・安全な管理者初期設定手順は未実装。
- メール確認の送信フロー、パスワード再設定/MFA、ログイン試行回数制限は未実装。
- localStorageのBearerはXSSに対して弱い。本番化ではHTTPSとHttpOnly Cookie等を含めて見直す。
- logout時に通信できない場合、端末の認証状態は破棄するがサーバー失効は保証できない。画面でその旨を表示する。盗まれたトークンがある場合は期限切れ/管理者による失効までリスクが残る。
- 期限切れ・失効セッションの定期削除は未実装。
- UUIDを数値変換してしまう一部画面の既存不整合は今回の認証変更の対象外。

参考: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
参考: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
