"""Idempotently initialize Metabase and seed the project dashboards."""
import os
import time

import requests

BASE = os.environ["METABASE_URL"].rstrip("/")
EMAIL = os.environ["METABASE_ADMIN_EMAIL"]
PASSWORD = os.environ["METABASE_ADMIN_PASSWORD"]
session = requests.Session()


def call(method, path, **kwargs):
    response = session.request(method, BASE + path, timeout=20, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"Metabase {method} {path}: {response.status_code} {response.text}")
    return response.json() if response.content else {}


for _ in range(180):
    try:
        if call("GET", "/api/health").get("status") == "ok":
            break
    except (requests.RequestException, RuntimeError):
        pass
    time.sleep(5)
else:
    raise TimeoutError("Metabase did not become healthy in 15 minutes")

props = call("GET", "/api/session/properties")
if props.get("has-user-setup"):
    auth = call("POST", "/api/session", json={"username": EMAIL, "password": PASSWORD})
else:
    auth = call("POST", "/api/setup", json={
        "token": props["setup-token"],
        "user": {"first_name": "Marketplace", "last_name": "Admin", "email": EMAIL, "password": PASSWORD},
        "prefs": {"site_name": "Marketplace Sport Analytics", "site_locale": "fr"},
    })
session.headers["X-Metabase-Session"] = auth["id"]

db_list = call("GET", "/api/database")
databases = db_list.get("data", db_list) if isinstance(db_list, dict) else db_list
db = next((item for item in databases if item.get("name") == "Marketplace Sport DWH"), None)
if not db:
    db = call("POST", "/api/database", json={
        "name": "Marketplace Sport DWH", "engine": "postgres",
        "details": {"host": "postgres-dwh", "port": 5432, "dbname": os.environ["POSTGRES_DWH_DB"],
                    "user": os.environ["POSTGRES_DWH_USER"], "password": os.environ["POSTGRES_DWH_PASSWORD"], "ssl": False},
        "is_full_sync": True, "is_on_demand": False,
    })
db_id = db["id"]

cards = [
    (
        "CA du dernier jour", "scalar",
        "SELECT COALESCE(SUM(total_revenue),0) AS ca_eur "
        "FROM analytics.daily_summary "
        "WHERE dt=(SELECT MAX(dt) FROM analytics.daily_summary)",
    ),
    (
        "Evolution du CA (30 jours)", "line",
        "SELECT dt, total_revenue AS ca_eur FROM analytics.daily_summary "
        "WHERE dt >= (SELECT MAX(dt)-29 FROM analytics.daily_summary) ORDER BY dt",
    ),
    (
        "Top 5 vendeurs du jour", "bar",
        "SELECT s.seller_name, SUM(sd.total_revenue) AS ca_eur "
        "FROM analytics.seller_daily sd JOIN dwh.dim_seller s USING(seller_id) "
        "WHERE sd.dt=(SELECT MAX(dt) FROM analytics.seller_daily) "
        "GROUP BY s.seller_id,s.seller_name ORDER BY ca_eur DESC LIMIT 5",
    ),
    (
        "Top 10 vendeurs du mois", "bar",
        "SELECT s.seller_name, SUM(sd.total_revenue) AS ca_eur "
        "FROM analytics.seller_daily sd JOIN dwh.dim_seller s USING(seller_id) "
        "WHERE sd.dt >= date_trunc('month',(SELECT MAX(dt) FROM analytics.seller_daily)::timestamp)::date "
        "GROUP BY s.seller_id,s.seller_name ORDER BY ca_eur DESC LIMIT 10",
    ),
    (
        "Evolution des 3 meilleurs vendeurs (30 jours)", "line",
        "WITH bounds AS (SELECT MAX(dt) AS max_dt FROM analytics.seller_daily), "
        "top_sellers AS (SELECT sd.seller_id FROM analytics.seller_daily sd, bounds b "
        "WHERE sd.dt >= b.max_dt-29 GROUP BY sd.seller_id "
        "ORDER BY SUM(sd.total_revenue) DESC, sd.seller_id LIMIT 3) "
        "SELECT sd.dt, s.seller_name, SUM(sd.total_revenue) AS ca_eur "
        "FROM analytics.seller_daily sd JOIN top_sellers t USING(seller_id) "
        "JOIN dwh.dim_seller s USING(seller_id) CROSS JOIN bounds b "
        "WHERE sd.dt >= b.max_dt-29 GROUP BY sd.dt,s.seller_id,s.seller_name "
        "ORDER BY sd.dt,s.seller_name",
    ),
    (
        "Vendeurs sans vente depuis 7 jours", "table",
        "SELECT s.seller_name, MAX(f.dt) AS derniere_vente FROM dwh.dim_seller s "
        "LEFT JOIN dwh.fact_orders f USING(seller_id) "
        "GROUP BY s.seller_id,s.seller_name "
        "HAVING MAX(f.dt) IS NULL OR MAX(f.dt)<(SELECT MAX(dt)-7 FROM dwh.fact_orders) "
        "ORDER BY derniere_vente NULLS FIRST",
    ),
    (
        "Commission par jour", "line",
        "SELECT dt, SUM(total_commission) AS commission_eur "
        "FROM analytics.seller_daily "
        "WHERE dt >= (SELECT MAX(dt)-29 FROM analytics.seller_daily) "
        "GROUP BY dt ORDER BY dt",
    ),
    (
        "CA par catégorie (30 jours)", "bar",
        "SELECT category, SUM(total_revenue) AS ca_eur FROM analytics.category_daily "
        "WHERE dt >= (SELECT MAX(dt)-29 FROM analytics.category_daily) "
        "GROUP BY category ORDER BY ca_eur DESC",
    ),
]
existing_cards_result = call("GET", "/api/card")
existing_cards = existing_cards_result.get("data", existing_cards_result) if isinstance(existing_cards_result, dict) else existing_cards_result
card_ids = {}
for name, display, sql in cards:
    card_payload = {
        "name": name,
        "type": "question",
        "display": display,
        "visualization_settings": {},
        "dataset_query": {"database": db_id, "type": "native", "native": {"query": sql}},
    }
    card = next((item for item in existing_cards if item.get("name") == name), None)
    if not card:
        card = call("POST", "/api/card", json=card_payload)
    else:
        # Update existing questions too, so a rerun fixes stale SQL and display settings.
        card = call("PUT", f"/api/card/{card['id']}", json=card_payload)
    card_ids[name] = card["id"]

dashboard_specs = [
    ("Executive Summary - Sport", ["CA du dernier jour", "Evolution du CA (30 jours)", "Top 5 vendeurs du jour"]),
    ("Top Sellers - Sport", ["Top 10 vendeurs du mois", "Evolution des 3 meilleurs vendeurs (30 jours)", "Vendeurs sans vente depuis 7 jours"]),
    ("Commissions - Sport", ["Commission par jour"]),
    ("Ventes par catégorie - Sport", ["CA par catégorie (30 jours)"]),
]
dashboard_list = call("GET", "/api/dashboard")
dashboards = dashboard_list.get("data", dashboard_list) if isinstance(dashboard_list, dict) else dashboard_list
for name, names in dashboard_specs:
    dashboard = next((item for item in dashboards if item.get("name") == name), None)
    if not dashboard:
        dashboard = call("POST", "/api/dashboard", json={"name": name, "description": "Dashboard provisionne pour Marketplace sport."})
    full = call("GET", f"/api/dashboard/{dashboard['id']}")
    existing_dashcards = {
        dashcard.get("card_id"): dashcard
        for dashcard in full.get("dashcards", [])
        if dashcard.get("card_id") is not None
    }
    dashcards = []
    for i, card_name in enumerate(names):
        card_id = card_ids[card_name]
        previous = existing_dashcards.get(card_id)
        dashcards.append({
            "id": previous["id"] if previous else -(i + 1),
            "card_id": card_id,
            "row": (i // 2) * 6,
            "col": (i % 2) * 12,
            "size_x": 12,
            "size_y": 6,
        })
    call("PUT", f"/api/dashboard/{dashboard['id']}", json={"dashcards": dashcards})
print("Metabase initialize : DWH connecte, 4 dashboards provisionnes ou actualises.")
