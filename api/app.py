"""Deterministic, authenticated sports marketplace API used by the project."""
from datetime import date as date_type
from datetime import timedelta
import hashlib
import os
import random

from flask import Flask, jsonify, request

app = Flask(__name__)
TOKEN = os.getenv("MARKETPLACE_API_TOKEN", "formation-token-2026")
SELLERS = [
    {"id": 1, "name": "Alpine Run", "country": "FR"},
    {"id": 2, "name": "VeloPro", "country": "FR"},
    {"id": 3, "name": "Outdoor Nord", "country": "BE"},
    {"id": 4, "name": "Fit & Forme", "country": "FR"},
    {"id": 5, "name": "Glisse Shop", "country": "CH"},
]
PRODUCTS = [
    {"id": 101, "name": "Chaussures trail", "category": "Course", "seller_id": 1, "price": 129.90},
    {"id": 102, "name": "Veste running", "category": "Course", "seller_id": 1, "price": 89.00},
    {"id": 201, "name": "Casque route", "category": "Cyclisme", "seller_id": 2, "price": 74.50},
    {"id": 202, "name": "Velo gravel", "category": "Cyclisme", "seller_id": 2, "price": 1199.00},
    {"id": 301, "name": "Sac randonnée 30L", "category": "Randonnée", "seller_id": 3, "price": 99.95},
    {"id": 302, "name": "Bâtons carbone", "category": "Randonnée", "seller_id": 3, "price": 119.00},
    {"id": 401, "name": "Tapis de yoga", "category": "Fitness", "seller_id": 4, "price": 39.90},
    {"id": 402, "name": "Haltères réglables", "category": "Fitness", "seller_id": 4, "price": 149.00},
    {"id": 501, "name": "Masque ski", "category": "Sports d'hiver", "seller_id": 5, "price": 69.90},
    {"id": 502, "name": "Casque ski", "category": "Sports d'hiver", "seller_id": 5, "price": 159.00},
]
CUSTOMERS = [{"id": i, "city": ["Paris", "Lyon", "Lille", "Bordeaux", "Nantes"][i % 5]} for i in range(1, 101)]


def _auth_required():
    if request.headers.get("Authorization") != f"Bearer {TOKEN}":
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.get("/health")
def health():
    return jsonify(status="ok", version="1.0.0")


@app.get("/sellers")
def sellers():
    denied = _auth_required()
    if denied:
        return denied
    limit = max(1, min(request.args.get("limit", 100, type=int), len(SELLERS)))
    return jsonify(SELLERS[:limit])


@app.get("/products")
def products():
    denied = _auth_required()
    if denied:
        return denied
    return jsonify(PRODUCTS)


@app.get("/customers")
def customers():
    denied = _auth_required()
    if denied:
        return denied
    limit = max(1, min(request.args.get("limit", 100, type=int), len(CUSTOMERS)))
    return jsonify(CUSTOMERS[:limit])


@app.get("/orders")
def orders():
    denied = _auth_required()
    if denied:
        return denied
    day = request.args.get("date", "")
    try:
        date_type.fromisoformat(day)
    except ValueError:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    rng = random.Random(int(hashlib.md5(day.encode()).hexdigest(), 16))
    result = []
    for index in range(rng.randint(70, 120)):
        product = rng.choice(PRODUCTS)
        quantity = rng.randint(1, 3)
        total = round(product["price"] * quantity, 2)
        result.append({
            "order_id": f"ORD-{day.replace('-', '')}-{index + 1:04d}",
            "date": day,
            "seller_id": product["seller_id"],
            "product_id": product["id"],
            "customer_id": rng.randint(1, len(CUSTOMERS)),
            "quantity": quantity,
            "total": total,
            "commission": round(total * 0.12, 2),
        })
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
