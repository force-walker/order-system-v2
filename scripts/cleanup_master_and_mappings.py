#!/usr/bin/env python3
"""Cleanup seeded test masters + supplier-product mappings by name prefix.

Default prefix: AUTOSEED
Deletes in safe order:
1) supplier-product mappings (for matching supplier/product)
2) suppliers
3) products
4) customers
"""

from __future__ import annotations

import argparse
import json
import urllib.error
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
    parser = argparse.ArgumentParser(description="Cleanup seeded masters and mappings")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ensure_health(args.base_url)

    deleted = {"mappings": 0, "suppliers": 0, "products": 0, "customers": 0}
    skipped = {"mappings": 0, "suppliers": 0, "products": 0, "customers": 0}

    # list all target entities
    _, customers = req(args.base_url, "GET", "/api/v1/customers")
    _, products = req(args.base_url, "GET", "/api/v1/products")
    _, suppliers = req(args.base_url, "GET", "/api/v1/suppliers")
    _, mappings = req(args.base_url, "GET", "/api/v1/supplier-product-mappings")

    target_customers = [c for c in customers if c.get("name", "").startswith(f"{args.prefix}-顧客")]
    target_products = [p for p in products if p.get("name", "").startswith(f"{args.prefix}-商品")]
    target_suppliers = [s for s in suppliers if s.get("name", "").startswith(f"{args.prefix}-仕入先")]

    target_product_ids = {p["id"] for p in target_products}
    target_supplier_ids = {s["id"] for s in target_suppliers}

    target_mappings = [
        m
        for m in mappings
        if m.get("supplier_id") in target_supplier_ids or m.get("product_id") in target_product_ids
    ]

    # 1) delete mappings first
    for m in target_mappings:
        if args.dry_run:
            skipped["mappings"] += 1
            continue
        st, _ = req(args.base_url, "DELETE", f"/api/v1/supplier-product-mappings/{m['id']}")
        if st in (200, 204):
            deleted["mappings"] += 1
        elif st == 404:
            skipped["mappings"] += 1
        else:
            raise RuntimeError(f"delete mapping failed id={m['id']} status={st}")

    # 2) suppliers
    for s in target_suppliers:
        if args.dry_run:
            skipped["suppliers"] += 1
            continue
        st, _ = req(args.base_url, "DELETE", f"/api/v1/suppliers/{s['id']}")
        if st in (200, 204):
            deleted["suppliers"] += 1
        elif st in (404, 409):
            skipped["suppliers"] += 1
        else:
            raise RuntimeError(f"delete supplier failed id={s['id']} status={st}")

    # 3) products
    for p in target_products:
        if args.dry_run:
            skipped["products"] += 1
            continue
        st, _ = req(args.base_url, "DELETE", f"/api/v1/products/{p['id']}")
        if st in (200, 204):
            deleted["products"] += 1
        elif st in (404, 409):
            skipped["products"] += 1
        else:
            raise RuntimeError(f"delete product failed id={p['id']} status={st}")

    # 4) customers
    for c in target_customers:
        if args.dry_run:
            skipped["customers"] += 1
            continue
        st, _ = req(args.base_url, "DELETE", f"/api/v1/customers/{c['id']}")
        if st in (200, 204):
            deleted["customers"] += 1
        elif st in (404, 409):
            skipped["customers"] += 1
        else:
            raise RuntimeError(f"delete customer failed id={c['id']} status={st}")

    print(
        json.dumps(
            {
                "base_url": args.base_url,
                "prefix": args.prefix,
                "dry_run": args.dry_run,
                "targets": {
                    "customers": len(target_customers),
                    "products": len(target_products),
                    "suppliers": len(target_suppliers),
                    "mappings": len(target_mappings),
                },
                "deleted": deleted,
                "skipped": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
