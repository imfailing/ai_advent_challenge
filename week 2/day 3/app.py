"""
Flask-приложение — маршруты и управление сессиями.
Возвращает детальные метрики токенов и стоимости для каждого ответа.
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
from agent import LLMAgent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

db.init_db()

_agents: dict[str, LLMAgent] = {}


def get_agent() -> LLMAgent:
    sid = session.get("id")
    if not sid:
        sid = str(uuid.uuid4())
        session["id"] = sid
    if sid not in _agents:
        _agents[sid] = LLMAgent(session_id=sid)
    return _agents[sid]


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
        "usage":       asdict(r.usage),    # метрики текущего запроса
        "session":     asdict(r.session),  # накопленные метрики сессии
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_history()
    return jsonify({"status": "ok"})


@app.route("/sessions")
def sessions():
    return jsonify(db.list_sessions())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
