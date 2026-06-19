"""
Flask-приложение — агент с явной трёхслойной моделью памяти.

Маршруты сгруппированы по слоям памяти:
  • краткосрочная — /ask, /clear
  • рабочая       — /memory/working (GET/POST/DELETE), /memory/task
  • долговременная— /memory/long-term (GET/POST), /memory/long-term/<id> (DELETE)
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
# Основные маршруты
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
        "memory":      asdict(r.memory),
    })


@app.route("/clear", methods=["POST"])
def clear():
    """Очистить ТОЛЬКО краткосрочную память (диалог)."""
    get_agent().clear_short_term()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Снимок всей памяти (для восстановления UI)
# ------------------------------------------------------------------

@app.route("/memory", methods=["GET"])
def get_memory():
    sid = get_agent().session_id
    return jsonify({
        "short_term_total": len(db.get_messages(sid)),
        "working_task":     db.get_active_task(sid),
        "working":          db.load_working(sid),
        "long_term":        db.load_long_term(sid),
        "auto_route":       get_agent().auto_route,
    })


@app.route("/memory/auto-route", methods=["POST"])
def set_auto_route():
    data = request.get_json(force=True)
    enabled = bool(data.get("enabled", True))
    get_agent().set_auto_route(enabled)
    return jsonify({"auto_route": enabled})


# ------------------------------------------------------------------
# РАБОЧАЯ память
# ------------------------------------------------------------------

@app.route("/memory/working", methods=["POST"])
def add_working():
    data  = request.get_json(force=True)
    key   = (data.get("key")   or "").strip()
    value = (data.get("value") or "").strip()
    if not key or not value:
        return jsonify({"error": "Нужны и ключ, и значение"}), 400
    sid  = get_agent().session_id
    db.upsert_working(sid, key, value, task=db.get_active_task(sid))
    return jsonify({"working": db.load_working(sid)})


@app.route("/memory/working/<path:key>", methods=["DELETE"])
def delete_working(key: str):
    sid   = get_agent().session_id
    found = db.delete_working_key(sid, key)
    if not found:
        return jsonify({"error": "Ключ не найден"}), 404
    return jsonify({"working": db.load_working(sid)})


@app.route("/memory/working", methods=["DELETE"])
def clear_working():
    """Завершить задачу — очистить всю рабочую память."""
    sid = get_agent().session_id
    db.clear_working(sid)
    db.set_active_task(sid, None)
    return jsonify({"status": "ok"})


@app.route("/memory/task", methods=["POST"])
def set_task():
    data = request.get_json(force=True)
    task = (data.get("task") or "").strip() or None
    sid  = get_agent().session_id
    db.set_active_task(sid, task)
    return jsonify({"task": task})


# ------------------------------------------------------------------
# ДОЛГОВРЕМЕННАЯ память
# ------------------------------------------------------------------

@app.route("/memory/long-term", methods=["POST"])
def add_long_term():
    data     = request.get_json(force=True)
    category = (data.get("category") or "").strip()
    content  = (data.get("content")  or "").strip()
    if category not in db.LONG_TERM_CATEGORIES:
        return jsonify({"error": f"Категория должна быть из {db.LONG_TERM_CATEGORIES}"}), 400
    if not content:
        return jsonify({"error": "Пустое содержимое"}), 400
    sid = get_agent().session_id
    db.add_long_term(sid, category, content)
    return jsonify({"long_term": db.load_long_term(sid)})


@app.route("/memory/long-term/<int:entry_id>", methods=["DELETE"])
def delete_long_term(entry_id: int):
    sid   = get_agent().session_id
    found = db.delete_long_term(entry_id, sid)
    if not found:
        return jsonify({"error": "Запись не найдена"}), 404
    return jsonify({"long_term": db.load_long_term(sid)})


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
    app.run(debug=True, port=5001)
