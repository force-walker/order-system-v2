#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "== seed test masters to: $BASE_URL =="

post_json() {
  local path="$1"
  local body="$2"

  status=$(curl -sS -o /tmp/seed_resp.json -w "%{http_code}" \
    -X POST "$BASE_URL$path" \
    -H "Content-Type: application/json" \
    -d "$body")

  if [[ "$status" == "201" || "$status" == "200" ]]; then
    echo "OK   POST $path"
  elif [[ "$status" == "409" ]]; then
    echo "SKIP POST $path (already exists)"
  else
    echo "FAIL POST $path (HTTP $status)"
    cat /tmp/seed_resp.json || true
    exit 1
  fi
}

# customers (3)
post_json "/api/v1/customers" '{"customer_code":"CUST-001","name":"テスト顧客A","active":true}'
post_json "/api/v1/customers" '{"customer_code":"CUST-002","name":"テスト顧客B","active":true}'
post_json "/api/v1/customers" '{"customer_code":"CUST-003","name":"テスト顧客C","active":true}'

# products (3)
post_json "/api/v1/products" '{"sku":"SKU-001","name":"鶏もも肉","order_uom":"kg","purchase_uom":"kg","invoice_uom":"kg","is_catch_weight":true,"weight_capture_required":true,"pricing_basis_default":"uom_kg"}'
post_json "/api/v1/products" '{"sku":"SKU-002","name":"玉ねぎ","order_uom":"kg","purchase_uom":"kg","invoice_uom":"kg","is_catch_weight":false,"weight_capture_required":false,"pricing_basis_default":"uom_count"}'
post_json "/api/v1/products" '{"sku":"SKU-003","name":"豚ロース","order_uom":"kg","purchase_uom":"kg","invoice_uom":"kg","is_catch_weight":false,"weight_capture_required":false,"pricing_basis_default":"uom_count"}'

echo "✅ seed complete"
