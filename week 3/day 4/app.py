"""
Flask-приложение — ассистент, работающий в рамках инвариантов.
Инварианты хранятся отдельно, инжектятся в каждый запрос, страж проверяет ответы.
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
from agent import LLMAgent
from models import MODELS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

db.init_db()

_agents: dict[str, LLMAgent] = {}


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Внутренняя ошибка сервера."}), 500


def get_agent() -> LLMAgent:
    sid = session.get("id")
    if not sid:
        sid = str(uuid.uuid4())
        session["id"] = sid
    if sid not in _agents:
        _agents[sid] = LLMAgent(session_id=sid)
    return _agents[sid]


# ------------------------------------------------------------------
# Чат
# ------------------------------------------------------------------

@app.route("/")
def index():
    get_agent()
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Пустой запрос"}), 400
    r = get_agent().ask(user_message)
    return jsonify({
        "answer":      r.answer,
        "model":       r.model,
        "elapsed_sec": r.elapsed_sec,
        "turn":        r.turn,
        "usage":       asdict(r.usage),
        "session":     asdict(r.session),
        "compliance":  asdict(r.compliance),
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_short_term()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Инварианты
# ------------------------------------------------------------------

@app.route("/invariants", methods=["GET"])
def list_invariants():
    sid = get_agent().session_id
    return jsonify({
        "invariants": db.list_invariants(sid),
        "categories": db.INVARIANT_CATEGORIES,
        "guard":      get_agent().guard_enabled,
    })


@app.route("/invariants", methods=["POST"])
def add_invariant():
    data     = request.get_json(force=True)
    category = (data.get("category") or "").strip()
    content  = (data.get("content")  or "").strip()
    if category not in db.INVARIANT_CATEGORIES:
        return jsonify({"error": f"Категория должна быть из {list(db.INVARIANT_CATEGORIES)}"}), 400
    if not content:
        return jsonify({"error": "Пустой инвариант"}), 400
    sid = get_agent().session_id
    inv = db.add_invariant(sid, category, content)
    return jsonify(inv)


@app.route("/invariants/<int:inv_id>/active", methods=["POST"])
def toggle_invariant(inv_id: int):
    data   = request.get_json(force=True)
    active = bool(data.get("active", True))
    sid    = get_agent().session_id
    if not db.set_invariant_active(inv_id, sid, active):
        return jsonify({"error": "Инвариант не найден"}), 404
    return jsonify({"id": inv_id, "active": active})


@app.route("/invariants/<int:inv_id>", methods=["DELETE"])
def delete_invariant(inv_id: int):
    sid = get_agent().session_id
    if not db.delete_invariant(inv_id, sid):
        return jsonify({"error": "Инвариант не найден"}), 404
    return jsonify({"status": "ok"})


@app.route("/guard", methods=["POST"])
def set_guard():
    data = request.get_json(force=True)
    enabled = bool(data.get("enabled", True))
    get_agent().set_guard(enabled)
    return jsonify({"guard": enabled})


# ------------------------------------------------------------------
# Модели
# ------------------------------------------------------------------

@app.route("/models")
def list_models():
    return jsonify([m.to_dict() for m in MODELS.values()])


@app.route("/model", methods=["GET"])
def get_model_route():
    return jsonify(get_agent().model_info.to_dict())


@app.route("/model", methods=["POST"])
def set_model_route():
    data     = request.get_json(force=True)
    model_id = (data.get("model_id") or "").strip()
    if not model_id:
        return jsonify({"error": "Не передан model_id"}), 400
    try:
        info = get_agent().set_model(model_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(info.to_dict())


if __name__ == "__main__":
    app.run(debug=True, port=5004)
