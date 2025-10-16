CREATE TABLE IF NOT EXISTS inventory (
    item_id SERIAL PRIMARY KEY,
    item_name TEXT NOT NULL UNIQUE,
    in_stock INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

INSERT INTO inventory (item_name, in_stock)
VALUES
    ('sprocket', 42),
    ('flux capacitor', 3),
    ('widget', 128)
ON CONFLICT (item_name)
DO UPDATE SET
    in_stock = EXCLUDED.in_stock,
    last_updated = NOW();
