#!/usr/bin/env python3
"""Seed test masters + supplier-product mappings for Order System v2.

Creates:
- customers: 5
- products: 10
- suppliers: 5
- random supplier-product mappings

Idempotency strategy:
- Uses deterministic names with prefix (default: AUTOSEED)
- Skips create when same-name record already exists
- Skips mapping create when same supplier/product pair already exists
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PREFIX = "AUTOSEED"


def req(base_url: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    r = urllib.request.Request(base_url + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = {"raw": raw}
        return e.code, payload


def ensure_health(base_url: str) -> None:
    status, payload = req(base_url, "GET", "/health")
    if status != 200:
        raise RuntimeError(f"health check failed: status={status} payload={payload}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed masters and supplier-product mappings")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--customers", type=int, default=5)
    parser.add_argument("--products", type=int, default=10)
    parser.add_argument("--suppliers", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-map-per-supplier", type=int, default=3)
    parser.add_argument("--max-map-per-supplier", type=int, default=6)
    args = parser.parse_args()

    random.seed(args.seed)
    ensure_health(args.base_url)

    created = {"customers": 0, "products": 0, "suppliers": 0, "mappings": 0}
    skipped = {"customers": 0, "products": 0, "suppliers": 0, "mappings": 0}

    # customers
    status, customers = req(args.base_url, "GET", "/api/v1/customers")
    if status != 200:
        raise RuntimeError(f"failed to list customers: {status} {customers}")
    by_name_customer = {c["name"]: c for c in customers}

    for i in range(1, args.customers + 1):
        name = f"{args.prefix}-顧客{i:02d}"
        if name in by_name_customer:
            skipped["customers"] += 1
            continue
        st, payload = req(args.base_url, "POST", "/api/v1/customers", {"name": name, "active": True})
        if st in (200, 201):
            created["customers"] += 1
        else:
            raise RuntimeError(f"create customer failed: {st} {payload}")

    # products
    status, products = req(args.base_url, "GET", "/api/v1/products")
    if status != 200:
        raise RuntimeError(f"failed to list products: {status} {products}")
    by_name_product = {p["name"]: p for p in products}

    uoms = ["kg", "case", "piece"]
    pricing_bases = ["uom_count", "uom_kg"]

    for i in range(1, args.products + 1):
        name = f"{args.prefix}-商品{i:02d}"
        if name in by_name_product:
            skipped["products"] += 1
            continue

        u = random.choice(uoms)
        payload = {
            "name": name,
            "order_uom": u,
            "purchase_uom": u,
            "invoice_uom": u,
            "is_catch_weight": random.choice([False, False, True]),
            "weight_capture_required": False,
            "pricing_basis_default": random.choice(pricing_bases),
        }
        st, data = req(args.base_url, "POST", "/api/v1/products", payload)
        if st in (200, 201):
            created["products"] += 1
        else:
            raise RuntimeError(f"create product failed: {st} {data}")

    # suppliers
    status, suppliers = req(args.base_url, "GET", "/api/v1/suppliers")
    if status != 200:
        raise RuntimeError(f"failed to list suppliers: {status} {suppliers}")
    by_name_supplier = {s["name"]: s for s in suppliers}

    for i in range(1, args.suppliers + 1):
        name = f"{args.prefix}-仕入先{i:02d}"
        if name in by_name_supplier:
            skipped["suppliers"] += 1
            continue
        st, data = req(args.base_url, "POST", "/api/v1/suppliers", {"name": name, "active": True})
        if st in (200, 201):
            created["suppliers"] += 1
        else:
            raise RuntimeError(f"create supplier failed: {st} {data}")

    # refresh IDs after creates
    _, customers = req(args.base_url, "GET", "/api/v1/customers")
    _, products = req(args.base_url, "GET", "/api/v1/products")
    _, suppliers = req(args.base_url, "GET", "/api/v1/suppliers")

    seeded_products = [p for p in products if p.get("name", "").startswith(f"{args.prefix}-商品")]
    seeded_suppliers = [s for s in suppliers if s.get("name", "").startswith(f"{args.prefix}-仕入先")]

    # existing mappings set
    status, mappings = req(args.base_url, "GET", "/api/v1/supplier-product-mappings")
    if status != 200:
        raise RuntimeError(f"failed to list mappings: {status} {mappings}")
    existing_pairs = {(m["supplier_id"], m["product_id"]) for m in mappings}

    product_ids = [p["id"] for p in seeded_products]
    if not product_ids:
        raise RuntimeError("no seeded products found; cannot create mappings")

    for s in seeded_suppliers:
        map_count = random.randint(args.min_map_per_supplier, args.max_map_per_supplier)
        sample = random.sample(product_ids, k=min(len(product_ids), map_count))
        for pid in sample:
            pair = (s["id"], pid)
            if pair in existing_pairs:
                skipped["mappings"] += 1
                continue
            payload = {
                "supplier_id": s["id"],
                "product_id": pid,
                "priority": random.randint(1, 200),
                "is_preferred": random.choice([True, False]),
                "default_unit_cost": round(random.uniform(10, 300), 2),
                "lead_time_days": random.randint(0, 7),
                "note": f"{args.prefix} auto-seeded mapping",
            }
            st, data = req(args.base_url, "POST", "/api/v1/supplier-product-mappings", payload)
            if st in (200, 201):
                created["mappings"] += 1
                existing_pairs.add(pair)
            elif st == 409:
                skipped["mappings"] += 1
            else:
                raise RuntimeError(f"create mapping failed: {st} {data}")

    result = {
        "base_url": args.base_url,
        "prefix": args.prefix,
        "created": created,
        "skipped": skipped,
        "totals": {
            "customers_seeded": len([c for c in customers if c.get("name", "").startswith(f"{args.prefix}-顧客")]),
            "products_seeded": len(seeded_products),
            "suppliers_seeded": len(seeded_suppliers),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
