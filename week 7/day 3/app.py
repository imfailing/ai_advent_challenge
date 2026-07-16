"""
Веб-интерфейс ассистента поддержки.

Пользователь выбирает тикет (или без него) и задаёт вопрос. Ассистент отвечает
по документации продукта (RAG) с учётом контекста тикета (тариф, проблема),
который берётся через MCP.
"""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from assistant import SupportAssistant

app = Flask(__name__)
DATA = Path(__file__).parent / "data" / "support.json"

_assistant: SupportAssistant | None = None


def get_assistant() -> SupportAssistant:
    global _assistant
    if _assistant is None:
        _assistant = SupportAssistant()
    return _assistant


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/tickets")
def tickets():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    out = []
    for t in data["tickets"].values():
        u = data["users"].get(t["user_id"], {})
        out.append({"id": t["id"], "subject": t["subject"],
                    "plan": u.get("plan"), "user": u.get("name")})
    return jsonify(out)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = (data.get("message") or "").strip()
    ticket_id = (data.get("ticket_id") or "").strip() or None
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return jsonify({"error": "Не задан DEEPSEEK_API_KEY."}), 503
    try:
        result = asyncio.run(get_assistant().ask(question, ticket_id=ticket_id))
    except Exception as e:
        return jsonify({"error": f"Ошибка: {e}"}), 500
    return jsonify(asdict(result))


if __name__ == "__main__":
    app.run(debug=True, port=5010)
