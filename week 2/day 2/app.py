"""
Flask-приложение — маршруты и управление сессиями.
Агент теперь восстанавливает историю из SQLite при каждом создании,
поэтому перезапуск сервера не обрывает диалог.
"""

import os
import uuid

from flask import Flask, jsonify, render_template, request, session

import database as db
from agent import LLMAgent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

# Инициализируем БД при старте приложения
db.init_db()

# Словарь session_id → LLMAgent (кэш в памяти процесса)
# Если агента нет в кэше — он создаётся заново и загружает историю из БД
_agents: dict[str, LLMAgent] = {}


def get_agent() -> LLMAgent:
    sid = session.get("id")
    if not sid:
        sid = str(uuid.uuid4())
        session["id"] = sid
    if sid not in _agents:
        # Агент сам загрузит историю из БД (даже после перезапуска)
        _agents[sid] = LLMAgent(session_id=sid)
    return _agents[sid]


@app.route("/")
def index():
    get_agent()  # убедиться, что сессия и агент инициализированы
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Пустой запрос"}), 400

    response = get_agent().ask(user_message)
    return jsonify({
        "answer": response.answer,
        "model": response.model,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "elapsed_sec": response.elapsed_sec,
        "turn": response.turn,
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_history()
    return jsonify({"status": "ok"})


@app.route("/sessions")
def sessions():
    """Список всех сохранённых сессий (для отладки/наглядности)."""
    return jsonify(db.list_sessions())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
