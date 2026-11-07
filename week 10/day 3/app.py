"""
HTTP-слой LLM-шлюза (Flask): только маршруты, вся логика — в gateway.py.

Маршруты: POST /chat (прокси в локальную LLM с Input/Output Guard), GET /health,
GET /audit?last=15 (хвост аудит-журнала), GET /stats (решения, токены, стоимость).
Запуск: `./venv/bin/python app.py` (порт из PORT, по умолчанию 5013).
"""

import os

from flask import Flask, jsonify, request

import audit
import gateway

app = Flask(__name__)
app.json.ensure_ascii = False  # читаемая кириллица в JSON-ответах


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    status, body = gateway.process(data, request.remote_addr or "unknown")
    response = jsonify(body)
    if status == 429:
        response.headers["Retry-After"] = str(body["retry_after"])
    return response, status


@app.route("/audit", methods=["GET"])
def audit_tail():
    try:
        last = max(1, min(int(request.args.get("last") or 15), 100))
    except (TypeError, ValueError):
        return jsonify({"error": "Параметр last должен быть числом."}), 400
    return jsonify({"entries": audit.tail(last)})


@app.route("/stats", methods=["GET"])
def stats():
    return jsonify(gateway.stats())


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5013")))
