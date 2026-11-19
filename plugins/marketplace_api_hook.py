"""Airflow Hook for the authenticated marketplace REST API."""
from datetime import date
import time

import requests
from airflow.sdk.bases.hook import BaseHook


class MarketplaceAPIHook(BaseHook):
    conn_name_attr = "marketplace_conn_id"
    default_conn_name = "marketplace_api"
    conn_type = "http"
    hook_name = "Marketplace API"

    def __init__(self, marketplace_conn_id="marketplace_api", retries=3, timeout=20):
        super().__init__()
        self.marketplace_conn_id = marketplace_conn_id
        self.retries = retries
        self.timeout = timeout

    def _get(self, endpoint, params=None):
        conn = self.get_connection(self.marketplace_conn_id)
        base = (conn.host or "").rstrip("/")
        if not base.startswith(("http://", "https://")):
            base = f"http://{base}"
        headers = {"Authorization": f"Bearer {conn.password}"}
        for attempt in range(self.retries):
            try:
                response = requests.get(f"{base}/{endpoint.lstrip('/')}", headers=headers,
                                        params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code < 500:
                    raise
                if attempt + 1 == self.retries:
                    raise
                time.sleep(2 ** attempt)

    def get_orders(self, order_date):
        return self._get("orders", {"date": str(order_date)})

    def get_sellers(self):
        return self._get("sellers", {"limit": 1000})

    def get_products(self):
        return self._get("products")

    def get_customers(self, limit=1000):
        return self._get("customers", {"limit": limit})
