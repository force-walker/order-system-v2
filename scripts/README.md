# scripts/README.md

テスト用データ投入・削除用の補助スクリプトです。

## 1) マスタ + マッピング投入

```bash
cd ~/.openclaw/workspace/order_system_v2
python3 scripts/seed_master_and_mappings.py
```

デフォルトで以下を作成します（`AUTOSEED-` 接頭辞付き）。
- 顧客 5件
- 商品 10件
- 仕入先 5件
- 仕入先×商品マッピング（ランダム）

### オプション例

```bash
python3 scripts/seed_master_and_mappings.py --base-url http://localhost:8000 --prefix AUTOSEED --seed 42
```

---

## 2) 投入データのクリーンアップ

```bash
python3 scripts/cleanup_master_and_mappings.py
```

`--prefix` に一致する投入データを削除します。
（削除順: マッピング → 仕入先 → 商品 → 顧客）

### Dry-run（削除せず対象確認）

```bash
python3 scripts/cleanup_master_and_mappings.py --dry-run
```

---

## 注意

- API (`http://localhost:8000`) が起動している必要があります。
- 本番データと区別するため、`--prefix` で明確に分離してください。
