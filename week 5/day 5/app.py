"""
Мини-чат на Flask: RAG + источники + память задачи.

Каждый вопрос: RAG-поиск в базе → ответ по контексту с источниками →
обновление памяти задачи (цель / уточнения / ограничения / термины).
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
from agent import ChatAgent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

db.init_db()

_agents: dict[str, ChatAgent] = {}


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Внутренняя ошибка сервера."}), 500


def get_agent() -> ChatAgent:
    sid = session.get("id")
    if not sid:
        sid = str(uuid.uuid4())
        session["id"] = sid
    if sid not in _agents:
        _agents[sid] = ChatAgent(session_id=sid)
    return _agents[sid]


@app.route("/")
def index():
    get_agent()
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = (data.get("message") or "").strip()
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400
    r = get_agent().ask(question)
    return jsonify({
        "answer":      r.answer,
        "sources":     r.sources,
        "found":       r.found,
        "top_score":   r.top_score,
        "task_memory": r.task_memory,
    })


@app.route("/memory")
def memory():
    return jsonify(db.get_task_memory(get_agent().session_id))


@app.route("/history")
def history():
    return jsonify(db.get_messages(get_agent().session_id))


@app.route("/clear", methods=["POST"])
def clear():
    db.clear_session(get_agent().session_id)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5006)
