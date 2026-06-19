"""
Flask-приложение — ассистент с контролируемым жизненным циклом задачи.
Явные переходы с гейтами: нельзя перепрыгнуть этап, нельзя финал без валидации.
"""

import os
import uuid
from dataclasses import asdict

from flask import Flask, jsonify, render_template, request, session

import database as db
import statemachine as sm
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
        "task_state":  r.task_state,
        "events":      r.events,
    })


@app.route("/clear", methods=["POST"])
def clear():
    get_agent().clear_short_term()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------------
# Жизненный цикл задачи
# ------------------------------------------------------------------

@app.route("/task", methods=["GET"])
def get_task():
    sid   = get_agent().session_id
    state = db.get_task_state(sid)
    # для каждого этапа — куда можно перейти и что блокирует
    transitions_map = {}
    if state:
        for frm in sm.STAGES:
            transitions_map[frm] = [
                {"to": to, "missing": [sm.GATES[g] for g in
                                       sm.missing_gates(frm, to, state["conditions"])]}
                for to in sm.allowed_targets(frm)
            ]
    return jsonify({
        "state":        state,
        "transitions":  db.get_transitions(sid),
        "stages":       sm.STAGES,
        "stage_labels": sm.STAGE_LABELS,
        "gates":        sm.GATES,
        "transitions_map": transitions_map,
        "auto_advance": get_agent().auto_advance,
    })


@app.route("/task/start", methods=["POST"])
def start_task():
    data = request.get_json(force=True)
    name = (data.get("task_name") or "").strip()
    if not name:
        return jsonify({"error": "Нужно название задачи"}), 400
    return jsonify(get_agent().start_task(name))


@app.route("/task/transition", methods=["POST"])
def transition_task():
    data     = request.get_json(force=True)
    to_stage = (data.get("to_stage") or "").strip()
    if not sm.is_stage(to_stage):
        return jsonify({"error": "Неизвестный этап"}), 400
    try:
        state = get_agent().transition(to_stage)
    except ValueError as e:
        # недопустимый переход — 422 с причиной
        return jsonify({"error": str(e), "rejected": True}), 422
    return jsonify(state)


@app.route("/task/condition", methods=["POST"])
def set_condition():
    data  = request.get_json(force=True)
    gate  = (data.get("gate") or "").strip()
    value = bool(data.get("value", True))
    if gate not in sm.GATES:
        return jsonify({"error": "Неизвестный гейт"}), 400
    state = get_agent().set_condition(gate, value)
    if not state:
        return jsonify({"error": "Задача не начата"}), 404
    return jsonify(state)


@app.route("/task/pause", methods=["POST"])
def pause_task():
    state = get_agent().pause()
    if not state:
        return jsonify({"error": "Задача не начата"}), 404
    return jsonify(state)


@app.route("/task/resume", methods=["POST"])
def resume_task():
    state = get_agent().resume()
    if not state:
        return jsonify({"error": "Задача не начата"}), 404
    return jsonify(state)


@app.route("/task/reset", methods=["POST"])
def reset_task():
    get_agent().reset_task()
    return jsonify({"status": "ok"})


@app.route("/task/auto-advance", methods=["POST"])
def set_auto_advance():
    data = request.get_json(force=True)
    enabled = bool(data.get("enabled", True))
    get_agent().set_auto_advance(enabled)
    return jsonify({"auto_advance": enabled})


# ------------------------------------------------------------------
# Память
# ------------------------------------------------------------------

@app.route("/memory", methods=["GET"])
def get_memory():
    sid = get_agent().session_id
    return jsonify({
        "short_term_total": len(db.get_messages(sid)),
        "working":          db.load_working(sid),
        "long_term":        db.load_long_term(sid),
    })


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
    app.run(debug=True, port=5005)
