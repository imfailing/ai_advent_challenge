"""
Веб-приложение (Flask) поверх ЛОКАЛЬНОЙ LLM (Ollama).

Полностью офлайн: никаких облачных API/ключей. Приложение отправляет запросы
в локальный Ollama-сервер, стримит ответы токен за токеном и отображает их.
"""

import json
import os
import uuid

from flask import Flask, Response, jsonify, render_template, request, session, stream_with_context

import database as db
import ollama_client as llm

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")

db.init_db()

HISTORY_TURNS = 10   # сколько последних сообщений отдаём модели как контекст


def _sid() -> str:
    sid = session.get("id")
    if not sid:
        sid = str(uuid.uuid4())
        session["id"] = sid
    return sid


@app.route("/")
def index():
    _sid()
    return render_template("index.html")


@app.route("/health")
def health():
    """Статус локального сервера и список моделей — без облака."""
    up = llm.is_up()
    return jsonify({"ollama_up": up,
                    "models": llm.list_models() if up else [],
                    "default": llm.DEFAULT_MODEL})


@app.route("/history")
def history():
    return jsonify(db.get_messages(_sid()))


@app.route("/clear", methods=["POST"])
def clear():
    db.clear(_sid())
    return jsonify({"status": "ok"})


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = (data.get("message") or "").strip()
    model = (data.get("model") or llm.DEFAULT_MODEL).strip()
    if not question:
        return jsonify({"error": "Пустой вопрос"}), 400
    if not llm.is_up():
        return jsonify({"error": "Локальный сервер Ollama недоступен "
                                 "(запустите Ollama)."}), 503

    sid = _sid()
    db.add_message(sid, "user", question)
    # контекст: последние N сообщений диалога
    messages = db.get_messages(sid)[-HISTORY_TURNS:]

    def generate():
        collected = []
        try:
            for part in llm.chat_stream(messages, model=model):
                if "token" in part:
                    collected.append(part["token"])
                    yield json.dumps({"token": part["token"]}) + "\n"
                elif part.get("done"):
                    yield json.dumps({"done": True, "stats": part["stats"]}) + "\n"
        except Exception as e:
            yield json.dumps({"error": f"Ошибка локальной модели: {e}"}) + "\n"
        finally:
            # сохранить полный ответ ассистента
            answer = "".join(collected).strip()
            if answer:
                db.add_message(sid, "assistant", answer)

    return Response(stream_with_context(generate()),
                    mimetype="application/x-ndjson")


if __name__ == "__main__":
    app.run(debug=True, port=5007)
