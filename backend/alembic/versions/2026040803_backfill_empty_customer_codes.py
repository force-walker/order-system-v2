"""backfill blank customer_code with sequential CUST-xxx

Revision ID: 2026040803
Revises: 2026040802
Create Date: 2026-04-08 23:18:00
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa


revision = "2026040803"
down_revision = "2026040802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    meta = sa.MetaData()
    customers = sa.Table(
        "customers",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_code", sa.String(64), nullable=False),
    )

    rows = bind.execute(sa.select(customers.c.id, customers.c.customer_code).order_by(customers.c.id.asc())).all()

    used_numbers: set[int] = set()
    blank_ids: list[int] = []
    pattern = re.compile(r"^CUST-(\d+)$")

    for row in rows:
        code = row.customer_code
        if code is None or str(code).strip() == "":
            blank_ids.append(row.id)
            continue
        m = pattern.match(str(code).strip())
        if m:
            used_numbers.add(int(m.group(1)))

    next_num = 1
    for customer_id in blank_ids:
        while next_num in used_numbers:
            next_num += 1
        new_code = f"CUST-{next_num:03d}"
        bind.execute(
            customers.update().where(customers.c.id == customer_id).values(customer_code=new_code)
        )
        used_numbers.add(next_num)
        next_num += 1


def downgrade() -> None:
    # irreversible data backfill
    pass
