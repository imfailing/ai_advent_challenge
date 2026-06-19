"""
Flask-приложение — персонализированный агент.
Модель памяти (day 1) + профиль пользователя, подключённый к каждому запросу.
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
# Чат
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
        "profile":     r.profile,
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_short_term()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Профили (персонализация)
# ------------------------------------------------------------------

@app.route("/profiles", methods=["GET"])
def list_profiles():
    sid = get_agent().session_id
    return jsonify({
        "profiles":   db.list_profiles(sid),
        "active_id":  db.get_active_profile_id(sid),
        "fields":     db.PROFILE_FIELDS,
        "enums": {
            "expertise": db.EXPERTISE_LEVELS,
            "tone":      db.TONES,
            "verbosity": db.VERBOSITY_LEVELS,
            "language":  db.LANGUAGES,
        },
    })


@app.route("/profiles", methods=["POST"])
def create_profile():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Нужно имя профиля"}), 400
    sid     = get_agent().session_id
    fields  = {k: v for k, v in data.items() if k in db.PROFILE_FIELDS}
    profile = db.create_profile(sid, name, **fields)
    # Первый созданный профиль делаем активным автоматически
    if db.get_active_profile_id(sid) is None:
        db.set_active_profile_id(sid, profile["id"])
    return jsonify(profile)


@app.route("/profiles/<int:profile_id>", methods=["PUT"])
def update_profile(profile_id: int):
    data   = request.get_json(force=True)
    sid    = get_agent().session_id
    fields = {k: v for k, v in data.items() if k in db.PROFILE_FIELDS or k == "name"}
    updated = db.update_profile(profile_id, sid, **fields)
    if not updated:
        return jsonify({"error": "Профиль не найден"}), 404
    return jsonify(updated)


@app.route("/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id: int):
    sid = get_agent().session_id
    if not db.delete_profile(profile_id, sid):
        return jsonify({"error": "Профиль не найден"}), 404
    if db.get_active_profile_id(sid) == profile_id:
        db.set_active_profile_id(sid, None)
    return jsonify({"status": "ok"})


@app.route("/profiles/activate", methods=["POST"])
def activate_profile():
    data = request.get_json(force=True)
    pid  = data.get("profile_id")
    sid  = get_agent().session_id
    if pid is not None:
        pid = int(pid)
        prof = db.get_profile(pid)
        if not prof or prof["session_id"] != sid:
            return jsonify({"error": "Профиль не найден"}), 404
    db.set_active_profile_id(sid, pid)
    return jsonify({"active_id": pid})


# ------------------------------------------------------------------
# Память (как в day 1, сокращённо)
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
    app.run(debug=True, port=5002)
