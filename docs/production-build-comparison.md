# 本番ビルド比較（2026-09-18）

業務コードや認証方式を変更せず、Frontendの開発モードによる差を比較する。
5173の開発版は維持し、5174で本番ビルドをVite preview配信する。
これは比較用であり、本番用Webサーバーへの移行ではない。Backendは従来の開発サービスを共用する。

## 起動

通常のstart-dev.shでAPIが動いていることが前提。

```bash
cd /home/ikedakojiro/Documents/ChatGPT/order_system_v2/frontend
VITE_API_BASE_URL='' VITE_USE_MOCK=false VITE_APP_BRANCH=codex/remote-development npm run build
systemd-run --user --unit=order-system-v2-preview --collect --working-directory=/home/ikedakojiro/Documents/ChatGPT/order_system_v2/frontend /usr/bin/npm run preview -- --host 100.115.155.118 --port 5174 --strictPort
```

VITE_USE_MOCK=falseを明示し、実APIを使う。既存Vite設定の/apiと/healthプロキシをpreviewが継承する。
Tailscale IPだけで待ち受け、LANやインターネットへ公開しない。
PC再起動後は再実行が必要。別途ビルドするとpreviewの配信内容も変わる。

## 別PCでの比較

- 開発版: http://100.115.155.118:5173/
- 本番ビルド比較版: http://100.115.155.118:5174/

ポートが違うため、比較版には既存アカウントで改めてログインする。新規登録は不要。
**両方とも同じDBを使うため、登録・更新は実データに反映される。比較では表示・移動だけを行う。**
同じPC・同じ回線で顧客→注文一覧を各3回試し、クリックからデータ表示までを比較する。
初回表示と2回目以降を分ける。5174だけ接続できなければTailscaleのポート制限等を確認し、無断でアクセス規則を拡張しない。
本番ビルドで開発用の二重Effect実行はなくなるが、注文ごとの明細通信は現行仕様のまま残る。

## 比較版だけ停止

```bash
systemctl --user stop order-system-v2-preview
```

stop-dev.shは比較版サービスを停止しない。比較終了時は上記コマンドで個別に停止する。
