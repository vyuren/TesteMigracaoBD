CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    delta_qty INTEGER NOT NULL CHECK (delta_qty <> 0),
    movement_type TEXT NOT NULL
        CHECK (movement_type IN ('OPENING', 'SALE', 'ADJUSTMENT', 'RETURN')),
    order_id TEXT REFERENCES orders(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(trim(reason)) >= 5),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (movement_type = 'SALE' AND order_id IS NOT NULL)
        OR movement_type IN ('OPENING', 'ADJUSTMENT', 'RETURN')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_opening_product
    ON inventory_movements(product_id)
    WHERE movement_type = 'OPENING';

CREATE UNIQUE INDEX IF NOT EXISTS ux_sale_order_product
    ON inventory_movements(order_id, product_id)
    WHERE movement_type = 'SALE';

CREATE INDEX IF NOT EXISTS ix_compat_bike
    ON compatibility(bike_id, product_id);

CREATE INDEX IF NOT EXISTS ix_products_category
    ON products(category, id);

CREATE INDEX IF NOT EXISTS ix_movements_product
    ON inventory_movements(product_id, id);
