"""Daily ELT: authenticated API -> MinIO raw -> PostgreSQL staging/DWH."""
from datetime import date, datetime, timedelta
import json
import os

import boto3
from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from marketplace_api_hook import MarketplaceAPIHook
from psycopg2.extras import execute_values


@dag(
    dag_id="marketplace_orders_ingest_daily",
    description="Archive sports marketplace orders then load an idempotent dimensional model",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-engineering", "retries": 2, "retry_delay": timedelta(minutes=1)}
)
def marketplace_orders_ingest_daily():
    @task
    def refresh_dimensions():
        hook = MarketplaceAPIHook()
        sellers = hook.get_sellers()
        products = hook.get_products()
        pg = PostgresHook(postgres_conn_id="marketplace_dwh")
        conn = pg.get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    execute_values(cur, """INSERT INTO dwh.dim_seller(seller_id,seller_name,country)
                        VALUES %s ON CONFLICT(seller_id) DO UPDATE SET seller_name=EXCLUDED.seller_name,country=EXCLUDED.country""",
                        [(s["id"], s["name"], s["country"]) for s in sellers])
                    execute_values(cur, """INSERT INTO dwh.dim_product(product_id,product_name,category,seller_id,unit_price)
                        VALUES %s ON CONFLICT(product_id) DO UPDATE SET product_name=EXCLUDED.product_name,
                        category=EXCLUDED.category,seller_id=EXCLUDED.seller_id,unit_price=EXCLUDED.unit_price""",
                        [(p["id"], p["name"], p["category"], p["seller_id"], p["price"]) for p in products])
        finally:
            conn.close()

    @task
    def archive_orders(ds=None):
        payload = MarketplaceAPIHook().get_orders(ds)
        key = f"raw/orders/dt={ds}/data.json"
        client = boto3.client(
            "s3", endpoint_url=os.environ["MINIO_ENDPOINT"],
            aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
            aws_secret_access_key=os.environ["MINIO_SECRET_KEY"], region_name="us-east-1")
        client.put_object(Bucket=os.environ.get("MINIO_BUCKET", "data-lake"), Key=key,
                          Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          ContentType="application/json")
        return key

    @task
    def load_staging(ds=None, key=None):
        client = boto3.client(
            "s3", endpoint_url=os.environ["MINIO_ENDPOINT"],
            aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
            aws_secret_access_key=os.environ["MINIO_SECRET_KEY"], region_name="us-east-1")
        obj = client.get_object(Bucket=os.environ.get("MINIO_BUCKET", "data-lake"), Key=key)
        rows = json.loads(obj["Body"].read())
        pg = PostgresHook(postgres_conn_id="marketplace_dwh")
        conn = pg.get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM staging.orders WHERE dt=%s", (ds,))
                    execute_values(cur, "INSERT INTO staging.orders(dt,order_id,payload) VALUES %s",
                                   [(ds, row["order_id"], json.dumps(row)) for row in rows])
        finally:
            conn.close()
        return len(rows)

    @task
    def transform_idempotently(ds=None):
        pg = PostgresHook(postgres_conn_id="marketplace_dwh")
        conn = pg.get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO dwh.dim_date(dt,year,month,day,day_of_week)
                        VALUES (%s, EXTRACT(YEAR FROM %s::date), EXTRACT(MONTH FROM %s::date),
                        EXTRACT(DAY FROM %s::date), EXTRACT(ISODOW FROM %s::date))
                        ON CONFLICT(dt) DO NOTHING""", (ds, ds, ds, ds, ds))
                    cur.execute("DELETE FROM dwh.fact_orders WHERE dt=%s", (ds,))
                    cur.execute("""INSERT INTO dwh.fact_orders
                        (order_id,dt,seller_id,product_id,customer_id,quantity,total,commission)
                        SELECT order_id,dt,(payload->>'seller_id')::int,(payload->>'product_id')::int,
                        (payload->>'customer_id')::int,(payload->>'quantity')::int,
                        (payload->>'total')::numeric,(payload->>'commission')::numeric
                        FROM staging.orders WHERE dt=%s""", (ds,))
                    rows_loaded = cur.rowcount

                    cur.execute("DELETE FROM analytics.daily_summary WHERE dt=%s", (ds,))
                    cur.execute("DELETE FROM analytics.seller_daily WHERE dt=%s", (ds,))
                    cur.execute("DELETE FROM analytics.category_daily WHERE dt=%s", (ds,))
                    cur.execute("""INSERT INTO analytics.daily_summary
                        (dt,total_orders,total_revenue,total_commission,average_basket,top_seller_id)
                        SELECT %s::date, COUNT(DISTINCT order_id), COALESCE(SUM(total),0),
                        COALESCE(SUM(commission),0), SUM(total)/NULLIF(COUNT(DISTINCT order_id),0),
                        (SELECT seller_id FROM dwh.fact_orders WHERE dt=%s GROUP BY seller_id
                         ORDER BY SUM(total) DESC, seller_id LIMIT 1)
                        FROM dwh.fact_orders WHERE dt=%s""", (ds, ds, ds))
                    cur.execute("""INSERT INTO analytics.seller_daily
                        (dt,seller_id,total_orders,total_revenue,total_commission)
                        SELECT dt,seller_id,COUNT(DISTINCT order_id),SUM(total),SUM(commission)
                        FROM dwh.fact_orders WHERE dt=%s GROUP BY dt,seller_id""", (ds,))
                    cur.execute("""INSERT INTO analytics.category_daily
                        (dt,category,total_revenue,total_commission,total_orders)
                        SELECT f.dt,p.category,SUM(f.total),SUM(f.commission),COUNT(DISTINCT f.order_id)
                        FROM dwh.fact_orders f JOIN dwh.dim_product p USING(product_id)
                        WHERE f.dt=%s GROUP BY f.dt,p.category""", (ds,))
                    return rows_loaded
        finally:
            conn.close()

    dimensions = refresh_dimensions()
    raw_key = archive_orders()
    staged = load_staging(key=raw_key)
    dimensions >> staged
    transform = transform_idempotently()
    staged >> transform


marketplace_orders_ingest_daily()
