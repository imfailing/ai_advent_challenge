"""
Flask-приложение — только UI и маршрутизация.
Вся логика LLM-вызовов и памяти диалога спрятана в LLMAgent.

Каждый браузер получает свой экземпляр агента (идентифицируется по
flask.session UUID), поэтому несколько пользователей не мешают друг другу.
"""

import os
import uuid

from flask import Flask, jsonify, render_template, request, session

from agent import LLMAgent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

# Словарь session_id → LLMAgent (хранится в памяти процесса)
_agents: dict[str, LLMAgent] = {}


def get_agent() -> LLMAgent:
    """Вернуть агента для текущей сессии браузера, создав его при необходимости."""
    sid = session.get("id")
    if not sid or sid not in _agents:
        sid = str(uuid.uuid4())
        session["id"] = sid
        _agents[sid] = LLMAgent()
    return _agents[sid]


@app.route("/")
def index():
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
    """Сбросить историю диалога текущей сессии."""
    get_agent().clear_history()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
