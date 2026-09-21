"""Scope order line number uniqueness to its parent order."""

from alembic import op
import sqlalchemy as sa


revision = "2026092001"
down_revision = "2026091901"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        unique_constraints = sa.inspect(bind).get_unique_constraints("order_items")
        old_constraint = next(
            (
                constraint["name"]
                for constraint in unique_constraints
                if constraint.get("column_names") == ["order_line_no"]
            ),
            None,
        )
        if old_constraint:
            op.drop_constraint(old_constraint, "order_items", type_="unique")
        op.create_index("ix_order_items_order_line_no", "order_items", ["order_line_no"], unique=False)
        op.create_unique_constraint(
            "uq_order_items_order_line_no_per_order",
            "order_items",
            ["order_id", "order_line_no"],
        )
        return

    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_index("ix_order_items_order_line_no")
        batch_op.create_index("ix_order_items_order_line_no", ["order_line_no"], unique=False)
        batch_op.create_unique_constraint("uq_order_items_order_line_no_per_order", ["order_id", "order_line_no"])


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("uq_order_items_order_line_no_per_order", "order_items", type_="unique")
        op.drop_index("ix_order_items_order_line_no", table_name="order_items")
        op.create_unique_constraint("uq_order_items_order_line_no", "order_items", ["order_line_no"])
        return

    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_constraint("uq_order_items_order_line_no_per_order", type_="unique")
        batch_op.drop_index("ix_order_items_order_line_no")
        batch_op.create_index("ix_order_items_order_line_no", ["order_line_no"], unique=True)
