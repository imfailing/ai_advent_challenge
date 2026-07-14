"""
Веб-интерфейс ассистента разработчика.

Команда /help — ассистент отвечает на вопросы о проекте, используя RAG по
документации (README + доки дней + claude/) и git-инструменты через MCP.
Генерация — облачная модель DeepSeek.

  /help              — что умеет ассистент
  /help <вопрос>     — ответ на вопрос о проекте
  <вопрос>           — то же (префикс /help необязателен)
"""

import asyncio
import os
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from assistant import DevAssistant

app = Flask(__name__)

_assistant: DevAssistant | None = None

HELP_TEXT = (
    "Я — ассистент разработчика этого проекта. Спросите меня о структуре, "
    "документации или состоянии репозитория. Примеры:\n\n"
    "- Что реализовано в неделе 5?\n"
    "- На какой ветке сейчас проект?\n"
    "- Какие последние коммиты?\n"
    "- Какие файлы в week 7/day 1?\n"
    "- Как устроена модель памяти агента?\n\n"
    "Я использую документацию проекта (RAG) и git (через MCP)."
)


def get_assistant() -> DevAssistant:
    global _assistant
    if _assistant is None:
        _assistant = DevAssistant()
    return _assistant


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()

    # команда /help
    if message.lower() == "/help" or not message:
        return jsonify({"answer": HELP_TEXT, "sources": [], "git_calls": [], "help": True})
    if message.lower().startswith("/help "):
        message = message[6:].strip()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        return jsonify({"error": "Не задан DEEPSEEK_API_KEY (нужна облачная модель)."}), 503

    try:
        result = asyncio.run(get_assistant().ask(message))
    except Exception as e:
        return jsonify({"error": f"Ошибка: {e}"}), 500
    return jsonify(asdict(result))


if __name__ == "__main__":
    app.run(debug=True, port=5009)
