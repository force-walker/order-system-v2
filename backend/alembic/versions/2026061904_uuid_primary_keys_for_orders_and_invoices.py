"""switch order/invoice aggregates to uuid primary keys

Revision ID: 2026061904
Revises: 2026061903
Create Date: 2026-06-19 22:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026061904"
down_revision = "2026061903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TABLE orders RENAME TO orders_old")
        op.execute("ALTER TABLE order_items RENAME TO order_items_old")
        op.execute("ALTER TABLE invoices RENAME TO invoices_old")
        op.execute("ALTER TABLE invoice_items RENAME TO invoice_items_old")
        op.execute("ALTER TABLE supplier_allocations RENAME TO supplier_allocations_old")
        op.execute("ALTER TABLE purchase_results RENAME TO purchase_results_old")
        op.execute("ALTER TABLE audit_logs RENAME TO audit_logs_old")

        op.execute(
            """
            CREATE TABLE orders (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                legacy_id INTEGER,
                tracking_no VARCHAR(32),
                order_no VARCHAR(64) NOT NULL,
                customer_id INTEGER NOT NULL,
                order_datetime TIMESTAMP NOT NULL,
                delivery_date DATE NOT NULL,
                shipped_date DATE,
                status VARCHAR(16) NOT NULL,
                note TEXT,
                created_by VARCHAR(64) NOT NULL,
                updated_by VARCHAR(64) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO orders (
                id, legacy_id, tracking_no, order_no, customer_id, order_datetime, delivery_date, shipped_date,
                status, note, created_by, updated_by, created_at, updated_at
            )
            SELECT
                uuid, id, tracking_no, order_no, customer_id, order_datetime, delivery_date, shipped_date,
                status::text, note, created_by, updated_by, created_at, updated_at
            FROM orders_old
            """
        )

        op.execute(
            """
            CREATE TABLE order_items (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                legacy_id INTEGER,
                order_id VARCHAR(36) NOT NULL,
                order_line_no VARCHAR(32),
                product_id INTEGER NOT NULL,
                ordered_qty NUMERIC(12,3) NOT NULL,
                order_uom_type VARCHAR(16) NOT NULL,
                estimated_weight_kg NUMERIC(12,3),
                actual_weight_kg NUMERIC(12,3),
                shipped_date DATE,
                target_price NUMERIC(12,2),
                price_ceiling NUMERIC(12,2),
                stockout_policy VARCHAR(16),
                pricing_basis VARCHAR(16) NOT NULL,
                unit_price_uom_count NUMERIC(12,2),
                unit_price_uom_kg NUMERIC(12,2),
                note TEXT,
                comment TEXT,
                line_status VARCHAR(16) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders (id),
                FOREIGN KEY(product_id) REFERENCES products (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO order_items (
                id, legacy_id, order_id, order_line_no, product_id, ordered_qty, order_uom_type,
                estimated_weight_kg, actual_weight_kg, shipped_date, target_price, price_ceiling,
                stockout_policy, pricing_basis, unit_price_uom_count, unit_price_uom_kg, note, comment,
                line_status, created_at, updated_at
            )
            SELECT
                oi.uuid, oi.id, o.uuid, oi.order_line_no, oi.product_id, oi.ordered_qty, oi.order_uom_type::text,
                oi.estimated_weight_kg, oi.actual_weight_kg, oi.shipped_date, oi.target_price, oi.price_ceiling,
                oi.stockout_policy::text, oi.pricing_basis::text, oi.unit_price_uom_count, oi.unit_price_uom_kg,
                oi.note, oi.comment, oi.line_status::text, oi.created_at, oi.updated_at
            FROM order_items_old oi
            JOIN orders_old o ON o.id = oi.order_id
            """
        )

        op.execute(
            """
            CREATE TABLE invoices (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                legacy_id INTEGER,
                invoice_no VARCHAR(64) NOT NULL,
                tracking_no VARCHAR(32),
                invoice_draft_no VARCHAR(32),
                official_invoice_no VARCHAR(32),
                customer_id INTEGER NOT NULL,
                invoice_date DATE NOT NULL,
                delivery_date DATE NOT NULL,
                due_date DATE,
                subtotal NUMERIC(12,2) NOT NULL,
                tax_total NUMERIC(12,2) NOT NULL,
                grand_total NUMERIC(12,2) NOT NULL,
                status VARCHAR(16) NOT NULL,
                is_locked BOOLEAN NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO invoices (
                id, legacy_id, invoice_no, tracking_no, invoice_draft_no, official_invoice_no, customer_id,
                invoice_date, delivery_date, due_date, subtotal, tax_total, grand_total, status, is_locked,
                created_at, updated_at
            )
            SELECT
                uuid, id, invoice_no, tracking_no, invoice_draft_no, official_invoice_no, customer_id,
                invoice_date, delivery_date, due_date, subtotal, tax_total, grand_total, status::text, is_locked,
                created_at, updated_at
            FROM invoices_old
            """
        )

        op.execute(
            """
            CREATE TABLE supplier_allocations (
                id INTEGER NOT NULL PRIMARY KEY,
                order_item_id VARCHAR(36) NOT NULL,
                suggested_supplier_id INTEGER,
                suggested_qty NUMERIC(12,3),
                final_supplier_id INTEGER,
                final_qty NUMERIC(12,3),
                final_uom VARCHAR(32),
                is_manual_override BOOLEAN NOT NULL,
                override_reason_code VARCHAR(64),
                target_price NUMERIC(12,2),
                stockout_policy VARCHAR(16),
                split_group_id VARCHAR(64),
                parent_allocation_id INTEGER,
                is_split_child BOOLEAN NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(order_item_id) REFERENCES order_items (id),
                FOREIGN KEY(parent_allocation_id) REFERENCES supplier_allocations (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO supplier_allocations (
                id, order_item_id, suggested_supplier_id, suggested_qty, final_supplier_id, final_qty, final_uom,
                is_manual_override, override_reason_code, target_price, stockout_policy, split_group_id,
                parent_allocation_id, is_split_child, created_at, updated_at
            )
            SELECT
                sa.id, oi.uuid, sa.suggested_supplier_id, sa.suggested_qty, sa.final_supplier_id, sa.final_qty, sa.final_uom,
                sa.is_manual_override, sa.override_reason_code, sa.target_price, sa.stockout_policy::text, sa.split_group_id,
                sa.parent_allocation_id, sa.is_split_child, sa.created_at, sa.updated_at
            FROM supplier_allocations_old sa
            JOIN order_items_old oi ON oi.id = sa.order_item_id
            """
        )

        op.execute(
            """
            CREATE TABLE purchase_results (
                id INTEGER NOT NULL PRIMARY KEY,
                allocation_id INTEGER NOT NULL,
                supplier_id INTEGER,
                purchased_qty NUMERIC(12,3) NOT NULL,
                purchased_uom VARCHAR(32) NOT NULL,
                invoice_qty NUMERIC(12,3),
                actual_weight_kg NUMERIC(12,3),
                unit_cost NUMERIC(12,2),
                final_unit_cost NUMERIC(12,2),
                shortage_qty NUMERIC(12,3),
                shortage_policy VARCHAR(32),
                result_status VARCHAR(32) NOT NULL,
                invoiceable_flag BOOLEAN NOT NULL,
                recorded_by VARCHAR(64),
                recorded_at TIMESTAMP NOT NULL,
                note TEXT,
                is_deferred BOOLEAN NOT NULL,
                defer_until TIMESTAMP,
                defer_reason VARCHAR(255),
                deferred_by VARCHAR(64),
                deferred_at TIMESTAMP,
                FOREIGN KEY(allocation_id) REFERENCES supplier_allocations (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO purchase_results (
                id, allocation_id, supplier_id, purchased_qty, purchased_uom, invoice_qty, actual_weight_kg,
                unit_cost, final_unit_cost, shortage_qty, shortage_policy, result_status, invoiceable_flag,
                recorded_by, recorded_at, note, is_deferred, defer_until, defer_reason, deferred_by, deferred_at
            )
            SELECT
                id, allocation_id, supplier_id, purchased_qty, purchased_uom, invoice_qty, actual_weight_kg,
                unit_cost, final_unit_cost, shortage_qty, shortage_policy::text, result_status::text, invoiceable_flag,
                recorded_by, recorded_at, note, is_deferred, defer_until, defer_reason, deferred_by, deferred_at
            FROM purchase_results_old
            """
        )

        op.execute(
            """
            CREATE TABLE invoice_items (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                legacy_id INTEGER,
                invoice_id VARCHAR(36) NOT NULL,
                order_item_id VARCHAR(36) NOT NULL,
                invoice_line_no VARCHAR(32),
                billable_qty NUMERIC(12,3) NOT NULL,
                billable_uom VARCHAR(32) NOT NULL,
                invoice_line_status VARCHAR(16) NOT NULL,
                sales_unit_price NUMERIC(12,2) NOT NULL,
                unit_cost_basis NUMERIC(12,2),
                source_purchase_unit_cost_jpy NUMERIC(12,2),
                line_amount NUMERIC(12,2) NOT NULL,
                tax_amount NUMERIC(12,2) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY(invoice_id) REFERENCES invoices (id),
                FOREIGN KEY(order_item_id) REFERENCES order_items (id)
            )
            """
        )
        op.execute(
            """
            INSERT INTO invoice_items (
                id, legacy_id, invoice_id, order_item_id, invoice_line_no, billable_qty, billable_uom,
                invoice_line_status, sales_unit_price, unit_cost_basis, source_purchase_unit_cost_jpy,
                line_amount, tax_amount, created_at, updated_at
            )
            SELECT
                ii.uuid, ii.id, i.uuid, oi.uuid, ii.invoice_line_no, ii.billable_qty, ii.billable_uom,
                ii.invoice_line_status::text, ii.sales_unit_price, ii.unit_cost_basis, ii.source_purchase_unit_cost_jpy,
                ii.line_amount, ii.tax_amount, ii.created_at, ii.updated_at
            FROM invoice_items_old ii
            JOIN invoices_old i ON i.id = ii.invoice_id
            JOIN order_items_old oi ON oi.id = ii.order_item_id
            """
        )

        op.execute(
            """
            CREATE TABLE audit_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64) NOT NULL,
                action VARCHAR(64) NOT NULL,
                before_json TEXT,
                after_json TEXT,
                reason_code VARCHAR(64),
                changed_by VARCHAR(64) NOT NULL,
                trace_id VARCHAR(64),
                request_id VARCHAR(64),
                job_id VARCHAR(64),
                changed_at TIMESTAMP NOT NULL
            )
            """
        )
        op.execute(
            """
            INSERT INTO audit_logs (
                id, entity_type, entity_id, action, before_json, after_json,
                reason_code, changed_by, trace_id, request_id, job_id, changed_at
            )
            SELECT
                id, entity_type, CAST(entity_id AS TEXT), action, before_json, after_json,
                reason_code, changed_by, trace_id, request_id, job_id, changed_at
            FROM audit_logs_old
            """
        )

        op.execute("DROP TABLE audit_logs_old")
        op.execute("DROP TABLE invoice_items_old")
        op.execute("DROP TABLE purchase_results_old")
        op.execute("DROP TABLE supplier_allocations_old")
        op.execute("DROP TABLE invoices_old")
        op.execute("DROP TABLE order_items_old")
        op.execute("DROP TABLE orders_old")

        op.create_unique_constraint("uq_orders_legacy_id", "orders", ["legacy_id"])
        op.create_unique_constraint("uq_orders_tracking_no", "orders", ["tracking_no"])
        op.create_unique_constraint("uq_orders_order_no", "orders", ["order_no"])
        op.create_index("ix_orders_legacy_id", "orders", ["legacy_id"])
        op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
        op.create_index("ix_orders_order_datetime", "orders", ["order_datetime"])
        op.create_index("ix_orders_delivery_date", "orders", ["delivery_date"])
        op.create_index("ix_orders_shipped_date", "orders", ["shipped_date"])
        op.create_index("ix_orders_status", "orders", ["status"])

        op.create_unique_constraint("uq_order_items_legacy_id", "order_items", ["legacy_id"])
        op.create_unique_constraint("uq_order_items_order_line_no", "order_items", ["order_line_no"])
        op.create_index("ix_order_items_legacy_id", "order_items", ["legacy_id"])
        op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
        op.create_index("ix_order_items_product_id", "order_items", ["product_id"])
        op.create_index("ix_order_items_line_status", "order_items", ["line_status"])

        op.create_unique_constraint("uq_invoices_legacy_id", "invoices", ["legacy_id"])
        op.create_unique_constraint("uq_invoices_invoice_no", "invoices", ["invoice_no"])
        op.create_unique_constraint("uq_invoices_invoice_draft_no", "invoices", ["invoice_draft_no"])
        op.create_unique_constraint("uq_invoices_official_invoice_no", "invoices", ["official_invoice_no"])
        op.create_index("ix_invoices_legacy_id", "invoices", ["legacy_id"])
        op.create_index("ix_invoices_tracking_no", "invoices", ["tracking_no"])
        op.create_index("ix_invoices_status", "invoices", ["status"])

        op.create_index("ix_supplier_allocations_order_item_id", "supplier_allocations", ["order_item_id"])
        op.create_index("ix_supplier_allocations_split_group_id", "supplier_allocations", ["split_group_id"])
        op.create_index("ix_supplier_allocations_parent_allocation_id", "supplier_allocations", ["parent_allocation_id"])
        op.create_index("ix_purchase_results_allocation_id", "purchase_results", ["allocation_id"])

        op.create_unique_constraint("uq_invoice_items_legacy_id", "invoice_items", ["legacy_id"])
        op.create_unique_constraint("uq_invoice_items_invoice_line_no", "invoice_items", ["invoice_line_no"])
        op.create_index("ix_invoice_items_legacy_id", "invoice_items", ["legacy_id"])
        op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
        op.create_index("ix_invoice_items_order_item_id", "invoice_items", ["order_item_id"])

        op.create_index("ix_audit_logs_entity_type_entity_id_changed_at", "audit_logs", ["entity_type", "entity_id", "changed_at"])
        op.create_index("ix_audit_logs_changed_by_changed_at", "audit_logs", ["changed_by", "changed_at"])
        op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])
        op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
        op.create_index("ix_audit_logs_job_id", "audit_logs", ["job_id"])
        return

    op.execute("PRAGMA foreign_keys=OFF")

    op.execute("ALTER TABLE orders RENAME TO orders_old")
    op.execute("ALTER TABLE order_items RENAME TO order_items_old")
    op.execute("ALTER TABLE invoices RENAME TO invoices_old")
    op.execute("ALTER TABLE invoice_items RENAME TO invoice_items_old")
    op.execute("ALTER TABLE supplier_allocations RENAME TO supplier_allocations_old")
    op.execute("ALTER TABLE audit_logs RENAME TO audit_logs_old")

    op.execute(
        """
        CREATE TABLE orders (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            legacy_id INTEGER UNIQUE,
            tracking_no VARCHAR(32),
            order_no VARCHAR(64) NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            order_datetime DATETIME NOT NULL,
            delivery_date DATE NOT NULL,
            shipped_date DATE,
            status VARCHAR(16) NOT NULL,
            note TEXT,
            created_by VARCHAR(64) NOT NULL,
            updated_by VARCHAR(64) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers (id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_orders_tracking_no ON orders (tracking_no)")
    op.execute("CREATE INDEX ix_orders_customer_id ON orders (customer_id)")
    op.execute("CREATE INDEX ix_orders_order_datetime ON orders (order_datetime)")
    op.execute("CREATE INDEX ix_orders_delivery_date ON orders (delivery_date)")
    op.execute("CREATE INDEX ix_orders_shipped_date ON orders (shipped_date)")
    op.execute("CREATE INDEX ix_orders_status ON orders (status)")
    op.execute("CREATE INDEX ix_orders_legacy_id ON orders (legacy_id)")

    op.execute(
        """
        INSERT INTO orders (
            id, legacy_id, tracking_no, order_no, customer_id, order_datetime, delivery_date, shipped_date,
            status, note, created_by, updated_by, created_at, updated_at
        )
        SELECT
            uuid, id, tracking_no, order_no, customer_id, order_datetime, delivery_date, shipped_date,
            status, note, created_by, updated_by, created_at, updated_at
        FROM orders_old
        """
    )

    op.execute(
        """
        CREATE TABLE order_items (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            legacy_id INTEGER UNIQUE,
            order_id VARCHAR(36) NOT NULL,
            order_line_no VARCHAR(32),
            product_id INTEGER NOT NULL,
            ordered_qty NUMERIC(12,3) NOT NULL,
            order_uom_type VARCHAR(16) NOT NULL,
            estimated_weight_kg NUMERIC(12,3),
            actual_weight_kg NUMERIC(12,3),
            shipped_date DATE,
            target_price NUMERIC(12,2),
            price_ceiling NUMERIC(12,2),
            stockout_policy VARCHAR(16),
            pricing_basis VARCHAR(16) NOT NULL,
            unit_price_uom_count NUMERIC(12,2),
            unit_price_uom_kg NUMERIC(12,2),
            note TEXT,
            comment TEXT,
            line_status VARCHAR(16) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders (id),
            FOREIGN KEY(product_id) REFERENCES products (id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_order_items_order_line_no ON order_items (order_line_no)")
    op.execute("CREATE INDEX ix_order_items_order_id ON order_items (order_id)")
    op.execute("CREATE INDEX ix_order_items_product_id ON order_items (product_id)")
    op.execute("CREATE INDEX ix_order_items_line_status ON order_items (line_status)")
    op.execute("CREATE INDEX ix_order_items_legacy_id ON order_items (legacy_id)")

    op.execute(
        """
        INSERT INTO order_items (
            id, legacy_id, order_id, order_line_no, product_id, ordered_qty, order_uom_type,
            estimated_weight_kg, actual_weight_kg, shipped_date, target_price, price_ceiling,
            stockout_policy, pricing_basis, unit_price_uom_count, unit_price_uom_kg, note, comment,
            line_status, created_at, updated_at
        )
        SELECT
            oi.uuid,
            oi.id,
            o.uuid,
            oi.order_line_no,
            oi.product_id,
            oi.ordered_qty,
            oi.order_uom_type,
            oi.estimated_weight_kg,
            oi.actual_weight_kg,
            oi.shipped_date,
            oi.target_price,
            oi.price_ceiling,
            oi.stockout_policy,
            oi.pricing_basis,
            oi.unit_price_uom_count,
            oi.unit_price_uom_kg,
            oi.note,
            oi.comment,
            oi.line_status,
            oi.created_at,
            oi.updated_at
        FROM order_items_old oi
        JOIN orders_old o ON o.id = oi.order_id
        """
    )

    op.execute(
        """
        CREATE TABLE invoices (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            legacy_id INTEGER UNIQUE,
            invoice_no VARCHAR(64) NOT NULL UNIQUE,
            tracking_no VARCHAR(32),
            invoice_draft_no VARCHAR(32),
            official_invoice_no VARCHAR(32),
            customer_id INTEGER NOT NULL,
            invoice_date DATE NOT NULL,
            delivery_date DATE NOT NULL,
            due_date DATE,
            subtotal NUMERIC(12,2) NOT NULL,
            tax_total NUMERIC(12,2) NOT NULL,
            grand_total NUMERIC(12,2) NOT NULL,
            status VARCHAR(16) NOT NULL,
            is_locked BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers (id)
        )
        """
    )
    op.execute("CREATE INDEX ix_invoices_tracking_no ON invoices (tracking_no)")
    op.execute("CREATE UNIQUE INDEX ix_invoices_invoice_draft_no ON invoices (invoice_draft_no)")
    op.execute("CREATE UNIQUE INDEX ix_invoices_official_invoice_no ON invoices (official_invoice_no)")
    op.execute("CREATE INDEX ix_invoices_status ON invoices (status)")
    op.execute("CREATE INDEX ix_invoices_legacy_id ON invoices (legacy_id)")

    op.execute(
        """
        INSERT INTO invoices (
            id, legacy_id, invoice_no, tracking_no, invoice_draft_no, official_invoice_no, customer_id,
            invoice_date, delivery_date, due_date, subtotal, tax_total, grand_total, status, is_locked,
            created_at, updated_at
        )
        SELECT
            uuid, id, invoice_no, tracking_no, invoice_draft_no, official_invoice_no, customer_id,
            invoice_date, delivery_date, due_date, subtotal, tax_total, grand_total, status, is_locked,
            created_at, updated_at
        FROM invoices_old
        """
    )

    op.execute(
        """
        CREATE TABLE supplier_allocations (
            id INTEGER NOT NULL PRIMARY KEY,
            order_item_id VARCHAR(36) NOT NULL,
            suggested_supplier_id INTEGER,
            suggested_qty NUMERIC(12,3),
            final_supplier_id INTEGER,
            final_qty NUMERIC(12,3),
            final_uom VARCHAR(32),
            is_manual_override BOOLEAN NOT NULL,
            override_reason_code VARCHAR(64),
            target_price NUMERIC(12,2),
            stockout_policy VARCHAR(16),
            split_group_id VARCHAR(64),
            parent_allocation_id INTEGER,
            is_split_child BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(order_item_id) REFERENCES order_items (id),
            FOREIGN KEY(parent_allocation_id) REFERENCES supplier_allocations (id)
        )
        """
    )
    op.execute("CREATE INDEX ix_supplier_allocations_order_item_id ON supplier_allocations (order_item_id)")
    op.execute("CREATE INDEX ix_supplier_allocations_split_group_id ON supplier_allocations (split_group_id)")
    op.execute("CREATE INDEX ix_supplier_allocations_parent_allocation_id ON supplier_allocations (parent_allocation_id)")

    op.execute(
        """
        INSERT INTO supplier_allocations (
            id, order_item_id, suggested_supplier_id, suggested_qty, final_supplier_id, final_qty, final_uom,
            is_manual_override, override_reason_code, target_price, stockout_policy, split_group_id,
            parent_allocation_id, is_split_child, created_at, updated_at
        )
        SELECT
            sa.id,
            oi.uuid,
            sa.suggested_supplier_id,
            sa.suggested_qty,
            sa.final_supplier_id,
            sa.final_qty,
            sa.final_uom,
            sa.is_manual_override,
            sa.override_reason_code,
            sa.target_price,
            sa.stockout_policy,
            sa.split_group_id,
            sa.parent_allocation_id,
            sa.is_split_child,
            sa.created_at,
            sa.updated_at
        FROM supplier_allocations_old sa
        JOIN order_items_old oi ON oi.id = sa.order_item_id
        """
    )

    op.execute(
        """
        CREATE TABLE invoice_items (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            legacy_id INTEGER UNIQUE,
            invoice_id VARCHAR(36) NOT NULL,
            order_item_id VARCHAR(36) NOT NULL,
            invoice_line_no VARCHAR(32),
            billable_qty NUMERIC(12,3) NOT NULL,
            billable_uom VARCHAR(32) NOT NULL,
            invoice_line_status VARCHAR(16) NOT NULL,
            sales_unit_price NUMERIC(12,2) NOT NULL,
            unit_cost_basis NUMERIC(12,2),
            source_purchase_unit_cost_jpy NUMERIC(12,2),
            line_amount NUMERIC(12,2) NOT NULL,
            tax_amount NUMERIC(12,2) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices (id),
            FOREIGN KEY(order_item_id) REFERENCES order_items (id)
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_invoice_items_invoice_line_no ON invoice_items (invoice_line_no)")
    op.execute("CREATE INDEX ix_invoice_items_invoice_id ON invoice_items (invoice_id)")
    op.execute("CREATE INDEX ix_invoice_items_order_item_id ON invoice_items (order_item_id)")
    op.execute("CREATE INDEX ix_invoice_items_legacy_id ON invoice_items (legacy_id)")

    op.execute(
        """
        INSERT INTO invoice_items (
            id, legacy_id, invoice_id, order_item_id, invoice_line_no, billable_qty, billable_uom,
            invoice_line_status, sales_unit_price, unit_cost_basis, source_purchase_unit_cost_jpy,
            line_amount, tax_amount, created_at, updated_at
        )
        SELECT
            ii.uuid,
            ii.id,
            i.uuid,
            oi.uuid,
            ii.invoice_line_no,
            ii.billable_qty,
            ii.billable_uom,
            ii.invoice_line_status,
            ii.sales_unit_price,
            ii.unit_cost_basis,
            ii.source_purchase_unit_cost_jpy,
            ii.line_amount,
            ii.tax_amount,
            ii.created_at,
            ii.updated_at
        FROM invoice_items_old ii
        JOIN invoices_old i ON i.id = ii.invoice_id
        JOIN order_items_old oi ON oi.id = ii.order_item_id
        """
    )

    op.execute(
        """
        CREATE TABLE audit_logs (
            id INTEGER NOT NULL PRIMARY KEY,
            entity_type VARCHAR(64) NOT NULL,
            entity_id VARCHAR(64) NOT NULL,
            action VARCHAR(64) NOT NULL,
            before_json TEXT,
            after_json TEXT,
            reason_code VARCHAR(64),
            changed_by VARCHAR(64) NOT NULL,
            trace_id VARCHAR(64),
            request_id VARCHAR(64),
            job_id VARCHAR(64),
            changed_at DATETIME NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_audit_logs_entity_type_entity_id_changed_at ON audit_logs (entity_type, entity_id, changed_at)")
    op.execute("CREATE INDEX ix_audit_logs_changed_by_changed_at ON audit_logs (changed_by, changed_at)")
    op.execute("CREATE INDEX ix_audit_logs_trace_id ON audit_logs (trace_id)")
    op.execute("CREATE INDEX ix_audit_logs_request_id ON audit_logs (request_id)")
    op.execute("CREATE INDEX ix_audit_logs_job_id ON audit_logs (job_id)")

    op.execute(
        """
        INSERT INTO audit_logs (
            id, entity_type, entity_id, action, before_json, after_json,
            reason_code, changed_by, trace_id, request_id, job_id, changed_at
        )
        SELECT
            id, entity_type, CAST(entity_id AS TEXT), action, before_json, after_json,
            reason_code, changed_by, trace_id, request_id, job_id, changed_at
        FROM audit_logs_old
        """
    )

    op.execute("DROP TABLE audit_logs_old")
    op.execute("DROP TABLE invoice_items_old")
    op.execute("DROP TABLE supplier_allocations_old")
    op.execute("DROP TABLE invoices_old")
    op.execute("DROP TABLE order_items_old")
    op.execute("DROP TABLE orders_old")
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise RuntimeError("2026061904 downgrade is not supported")
