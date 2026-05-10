import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id BIGINT PRIMARY KEY,
            name TEXT,
            category TEXT,
            price INTEGER,
            old_price INTEGER,
            stock INTEGER,
            description TEXT,
            image TEXT,
            active BOOLEAN DEFAULT TRUE
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Premium Store API is running"})


@app.route("/products", methods=["GET"])
def get_products():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products ORDER BY id DESC")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    products = []
    for p in rows:
        products.append({
            "id": p["id"],
            "name": p["name"] or "",
            "category": p["category"] or "Новинки",
            "price": p["price"] or 0,
            "oldPrice": p["old_price"] or "",
            "stock": p["stock"] or 0,
            "desc": p["description"] or "",
            "image": p["image"] or "",
            "active": p["active"],
        })

    return jsonify(products)


@app.route("/products", methods=["POST"])
def add_product():
    data = request.json or {}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products 
        (id, name, category, price, old_price, stock, description, image, active)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            price = EXCLUDED.price,
            old_price = EXCLUDED.old_price,
            stock = EXCLUDED.stock,
            description = EXCLUDED.description,
            image = EXCLUDED.image,
            active = EXCLUDED.active
    """, (
        int(data.get("id")),
        data.get("name", ""),
        data.get("category", "Новинки"),
        int(data.get("price") or 0),
        int(data.get("oldPrice") or 0) if data.get("oldPrice") else None,
        int(data.get("stock") or 0),
        data.get("desc", ""),
        data.get("image", ""),
        bool(data.get("active", True)),
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})


@app.route("/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.json or {}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE products SET
            name=%s,
            category=%s,
            price=%s,
            old_price=%s,
            stock=%s,
            description=%s,
            image=%s,
            active=%s
        WHERE id=%s
    """, (
        data.get("name", ""),
        data.get("category", "Новинки"),
        int(data.get("price") or 0),
        int(data.get("oldPrice") or 0) if data.get("oldPrice") else None,
        int(data.get("stock") or 0),
        data.get("desc", ""),
        data.get("image", ""),
        bool(data.get("active", True)),
        int(product_id),
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})


@app.route("/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM products WHERE id=%s", (int(product_id),))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    print("SERVER STARTED WITH POSTGRES")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
