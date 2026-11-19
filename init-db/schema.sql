CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS staging.orders (
    dt date NOT NULL,
    order_id text NOT NULL,
    payload jsonb NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dt, order_id)
);

CREATE TABLE IF NOT EXISTS dwh.dim_seller (
    seller_id integer PRIMARY KEY,
    seller_name text NOT NULL,
    country text NOT NULL
);
CREATE TABLE IF NOT EXISTS dwh.dim_product (
    product_id integer PRIMARY KEY,
    product_name text NOT NULL,
    category text NOT NULL,
    seller_id integer NOT NULL REFERENCES dwh.dim_seller(seller_id),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0)
);
CREATE TABLE IF NOT EXISTS dwh.dim_date (
    dt date PRIMARY KEY,
    year smallint NOT NULL,
    month smallint NOT NULL,
    day smallint NOT NULL,
    day_of_week smallint NOT NULL
);
-- Grain: one row per purchased product line. order_id identifies the order.
CREATE TABLE IF NOT EXISTS dwh.fact_orders (
    order_id text NOT NULL,
    dt date NOT NULL REFERENCES dwh.dim_date(dt),
    seller_id integer NOT NULL REFERENCES dwh.dim_seller(seller_id),
    product_id integer NOT NULL REFERENCES dwh.dim_product(product_id),
    customer_id integer NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    total numeric(14,2) NOT NULL CHECK (total >= 0),
    commission numeric(14,2) NOT NULL CHECK (commission >= 0),
    PRIMARY KEY (order_id, product_id)
);
CREATE INDEX IF NOT EXISTS fact_orders_dt_idx ON dwh.fact_orders(dt);
CREATE INDEX IF NOT EXISTS fact_orders_seller_dt_idx ON dwh.fact_orders(seller_id, dt);

CREATE TABLE IF NOT EXISTS analytics.daily_summary (
    dt date PRIMARY KEY,
    total_orders integer NOT NULL,
    total_revenue numeric(16,2) NOT NULL,
    total_commission numeric(16,2) NOT NULL,
    average_basket numeric(16,2),
    top_seller_id integer REFERENCES dwh.dim_seller(seller_id)
);
CREATE TABLE IF NOT EXISTS analytics.seller_daily (
    dt date NOT NULL REFERENCES dwh.dim_date(dt),
    seller_id integer NOT NULL REFERENCES dwh.dim_seller(seller_id),
    total_orders integer NOT NULL,
    total_revenue numeric(16,2) NOT NULL,
    total_commission numeric(16,2) NOT NULL,
    PRIMARY KEY (dt, seller_id)
);
CREATE TABLE IF NOT EXISTS analytics.category_daily (
    dt date NOT NULL REFERENCES dwh.dim_date(dt),
    category text NOT NULL,
    total_revenue numeric(16,2) NOT NULL,
    total_commission numeric(16,2) NOT NULL,
    total_orders integer NOT NULL,
    PRIMARY KEY (dt, category)
);
