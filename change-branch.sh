#!/usr/bin/env bash
set -euo pipefail

read -rp "branch名を入力してください: " BRANCH

if [ -z "$BRANCH" ]; then
  echo "ERROR: branch名が空です"
  exit 1
fi

cd ~/.openclaw/workspace/order_system_v2

git fetch origin

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "==> 既存のローカルブランチに切り替え"
  git switch "$BRANCH"
  git pull
else
  echo "==> リモートブランチから新規作成して切り替え"
  git switch -c "$BRANCH" --track "origin/$BRANCH"
fi

cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
