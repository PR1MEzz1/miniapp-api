from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")


def load_products():
    try:
        if not os.path.exists(PRODUCTS_FILE):
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except:
        return []


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=4)


@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(load_products())


@app.route("/products", methods=["POST"])
def add_product():
    try:
        data = request.json

        products = load_products()

        products.append(data)

        save_products(products)

        return jsonify({
            "success": True,
            "products": products
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    try:
        data = request.json

        products = load_products()

        for i, product in enumerate(products):
            if str(product.get("id")) == str(product_id):
                products[i] = data

        save_products(products)

        return jsonify({
            "success": True
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    try:
        products = load_products()

        products = [
            p for p in products
            if str(p.get("id")) != str(product_id)
        ]

        save_products(products)

        return jsonify({
            "success": True
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


if __name__ == "__main__":
    print("SERVER STARTED")
    app.run(host="0.0.0.0", port=5000)