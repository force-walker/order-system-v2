# 外出先からの開発環境アクセス

更新: 2026-09-17

## 作業場所

今後の作業場所は `/home/ikedakojiro/Documents/ChatGPT/order_system_v2`。
OpenClaw 側の Git コミット `191a461` から履歴と管理済みファイルを引き継いだ。
元のフォルダは退避用として残す。両方のフォルダから同時に起動しない。
`backend/.env` は表示・コピーしていない。新しい開発起動手順も元の `.env` に依存しない。
これは同じPC上の作業場所変更であり、クラウドへの移行ではない。

## 接続

別ユーザーへの案内とChatGPTへ渡す説明文は [remote-user-guide.md](remote-user-guide.md) を参照。

1. ホストPCの電源・ネット接続・Tailscaleを維持する。スリープ中は使えない。
2. 接続端末にも Tailscale を導入し、許可された同じ tailnet に接続するか、ホストPCの端末共有招待を自分のアカウントで承認する。
3. ブラウザで `http://100.115.155.118:5173` を開く。

ホスト内でも同じ `http://100.115.155.118:5173` を使う。
通信経路は「接続端末 → Tailscale 専用IPの Vite → FastAPI」。
API `/api` と `/health` は Vite が `127.0.0.1:8000` に転送する。
接続端末側の localhost にアクセスしないため、CORS設定の追加は不要。
ViteはTailscaleのIPv4だけで待ち受け、API・PostgreSQL・Redisはループバックのみ。
LANのIPやルーターのポート転送からは利用しない。

## 起動・停止

```bash
cd /home/ikedakojiro/Documents/ChatGPT/order_system_v2
./start-dev.sh
./stop-dev.sh
```

起動は Docker Compose 1.x、ユーザー systemd、既存の外部 Python venv、Node/npm を使う。
このPCのDockerとの互換性のため `COMPOSE_API_VERSION=1.44` を指定する。
DBは既存の `order_system_v2_pgdata` を外部ボリュームとして再利用する。
存在しない場合は失敗するため、新規PCではDBの復元・準備が別途必要。
DB・Redisの既存コンテナは必要に応じて再作成するが、DBボリュームは保持する。
`.local/backups/` に起動前のDBダンプを保存してから Alembic を実行する。
バックアップはGit対象外。業務データを含むため共有しない。

APIと画面はユーザーサービスで動作し、起動に使った端末を閉じても継続する。
PC再起動後はログインして `./start-dev.sh` を再実行する。
ログアウト後の継続はユーザー systemd の設定次第。自動起動は設定していない。
停止スクリプトはDBを削除しない。旧 runbook の `down -v` はデータを消すため使わない。

起動時に `tailscale ip -4` で取得したアドレスを使う。IPが変わった場合は起動時に表示されたURLを使う。
Tailscale Serveは管理者パスワードが必要なため設定していない。
ホスト内だけで作業したい場合:

```bash
ORDER_SYSTEM_DEV_HOST=127.0.0.1 ./start-dev.sh
```

この場合は `http://localhost:5173` から使う。通常の `./start-dev.sh` で外出先利用に戻る。
IPアドレス形式のURLを利用する。MagicDNS名で利用する場合は Vite のホスト許可設定も確認する。
Funnelによるインターネット公開は設定しない。

## 確認・ログ

```bash
curl --fail http://100.115.155.118:5173/health
systemctl --user status order-system-v2-api order-system-v2-frontend
journalctl --user -u order-system-v2-api -u order-system-v2-frontend -n 50
tailscale status
```

接続できない場合はホストのスリープ、接続端末のTailscaleログイン、tailnetのアクセス規則、上記サービスの状態を確認する。
別端末からの最終確認では画面表示、マスタ一覧、注文画面の読込まで確認する。

2026-09-19 の確認結果: Backend 230件成功・PostgreSQL専用7件skip、Frontend 100件成功、型チェックとビルドが成功。
Tailscale用IPのURLでAPIヘルスチェック、ログイン、注文作成・一覧表示を確認した。
別PC・別Wi-Fiからの接続と業務画面表示も利用者が確認済み。ビルドには既存の大きなJSバンドルに関する警告がある。
起動前DBバックアップ後、Alembic headまで適用済み。

## 費用と利用範囲

クラウドサーバーの契約は不要。既存PCの電気代・回線費用は必要。
Tailscale Personalは公式料金表上 $0。適用条件・上限は契約に従う。
個人利用と会社・チーム利用ではプラン条件が異なるため、業務共有時は確認する。
料金参照: https://tailscale.com/pricing （2026-09-17確認）

APIログインはuser_id/password方式。旧user_id/role方式・自動ログインは廃止した。
詳細は [authentication.md](authentication.md) を参照。新規登録はorder_entry固定で、Customerとは独立。
tailnet内の信頼できる開発端末だけで利用する。顧客別の権限制御などは引き続き本番提供前の課題。
`npm run build` の生成物を単体配信する場合は `/api` のリバースプロキシを別途設定する。
