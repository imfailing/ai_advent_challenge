"""
Flask-приложение — маршруты и управление сессиями.
Три стратегии контекста: sliding_window, sticky_facts, branching.
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
import file_parser
from agent import LLMAgent, STRATEGIES
from models import MODELS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-in-prod")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

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
        "context":     asdict(r.context),
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_history()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Стратегии
# ------------------------------------------------------------------

@app.route("/strategy", methods=["GET"])
def get_strategy():
    agent = get_agent()
    return jsonify({
        "strategy":  agent.strategy,
        "branch_id": agent.branch_id,
    })


@app.route("/strategy", methods=["POST"])
def set_strategy():
    data     = request.get_json(force=True)
    strategy = (data.get("strategy") or "").strip()
    if strategy not in STRATEGIES:
        return jsonify({"error": f"Неизвестная стратегия. Доступны: {STRATEGIES}"}), 400
    try:
        get_agent().set_strategy(strategy)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify({"strategy": strategy})


# ------------------------------------------------------------------
# Ветки (Branching)
# ------------------------------------------------------------------

@app.route("/branches", methods=["GET"])
def list_branches():
    return jsonify(get_agent().list_branches())


@app.route("/branches", methods=["POST"])
def create_branch():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Не передано название ветки"}), 400
    try:
        branch = get_agent().create_branch(name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(branch)


@app.route("/branches/switch", methods=["POST"])
def switch_branch():
    data      = request.get_json(force=True)
    branch_id = data.get("branch_id")   # None или int
    if branch_id is not None:
        try:
            branch_id = int(branch_id)
        except (TypeError, ValueError):
            return jsonify({"error": "branch_id должен быть числом или null"}), 400
    try:
        info = get_agent().switch_branch(branch_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(info)


# ------------------------------------------------------------------
# Факты (Sticky Facts)
# ------------------------------------------------------------------

@app.route("/facts", methods=["GET"])
def get_facts():
    sid   = get_agent().session_id
    facts = db.load_facts(sid)
    return jsonify(facts)


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


# ------------------------------------------------------------------
# Файлы контекста
# ------------------------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Файл не передан"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Пустое имя файла"}), 400
    try:
        content = file_parser.extract_text(f.filename, f.read())
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    sid     = get_agent().session_id
    file_id = db.save_context_file(sid, f.filename, content)
    return jsonify({
        "id":         file_id,
        "filename":   f.filename,
        "size_chars": len(content),
        "preview":    content[:200].replace("\n", " "),
    })


@app.route("/context", methods=["GET"])
def list_context():
    sid   = get_agent().session_id
    files = db.load_context_files(sid)
    return jsonify([
        {"id": f["id"], "filename": f["filename"],
         "size_chars": f["size_chars"], "created_at": f["created_at"]}
        for f in files
    ])


@app.route("/context/<int:file_id>", methods=["DELETE"])
def delete_context(file_id: int):
    sid   = get_agent().session_id
    found = db.delete_context_file(file_id, sid)
    if not found:
        return jsonify({"error": "Файл не найден"}), 404
    return jsonify({"status": "ok"})


@app.route("/sessions")
def sessions():
    return jsonify(db.list_sessions())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
