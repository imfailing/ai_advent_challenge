"""
Flask-приложение — маршруты и управление сессиями.
Возвращает детальные метрики токенов и стоимости для каждого ответа.
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
import file_parser
from agent import LLMAgent
from models import MODELS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

db.init_db()

_agents: dict[str, LLMAgent] = {}


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Файл слишком большой. Максимум — 5 MB."}), 413


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


@app.route("/upload", methods=["POST"])
def upload():
    """Загрузить файл контекста и добавить его в сессию агента."""
    if "file" not in request.files:
        return jsonify({"error": "Файл не передан"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Пустое имя файла"}), 400

    try:
        content = file_parser.extract_text(f.filename, f.read())
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    sid = get_agent().session_id
    file_id = db.save_context_file(sid, f.filename, content)
    return jsonify({
        "id":         file_id,
        "filename":   f.filename,
        "size_chars": len(content),
        "preview":    content[:200].replace("\n", " "),
    })


@app.route("/context", methods=["GET"])
def list_context():
    """Список загруженных файлов контекста текущей сессии."""
    sid = get_agent().session_id
    files = db.load_context_files(sid)
    # Не возвращаем полный content в листинге — только метаданные
    return jsonify([
        {"id": f["id"], "filename": f["filename"],
         "size_chars": f["size_chars"], "created_at": f["created_at"]}
        for f in files
    ])


@app.route("/context/<int:file_id>", methods=["DELETE"])
def delete_context(file_id: int):
    """Удалить файл контекста по id."""
    sid = get_agent().session_id
    found = db.delete_context_file(file_id, sid)
    if not found:
        return jsonify({"error": "Файл не найден"}), 404
    return jsonify({"status": "ok"})


@app.route("/models")
def list_models():
    """Список доступных моделей с параметрами."""
    return jsonify([m.to_dict() for m in MODELS.values()])


@app.route("/model", methods=["GET"])
def get_model_route():
    """Параметры активной модели текущей сессии."""
    return jsonify(get_agent().model_info.to_dict())


@app.route("/model", methods=["POST"])
def set_model_route():
    """Переключить модель для текущей сессии."""
    data = request.get_json(force=True)
    model_id = (data.get("model_id") or "").strip()
    if not model_id:
        return jsonify({"error": "Не передан model_id"}), 400
    try:
        info = get_agent().set_model(model_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(info.to_dict())


@app.route("/sessions")
def sessions():
    return jsonify(db.list_sessions())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
