"""
Приватный AI-сервис на базе локальной LLM (Ollama).

HTTP API + веб-чат. Модель сервится локально на том же хосте (VPS) через Ollama;
этот сервис добавляет поверх: аутентификацию по API-ключу, rate limit,
ограничение контекста, стриминг и простой UI.

Эндпоинты:
  GET  /                 — веб-чат (UI)
  GET  /v1/health        — статус (без auth): доступность Ollama, модель
  GET  /v1/models        — список локальных моделей (auth)
  POST /v1/chat          — чат со стримингом NDJSON (auth + rate limit + лимиты)

Аутентификация: заголовок  Authorization: Bearer <API_KEY>
(если API_KEYS не заданы — auth выключен, только для локальной разработки).
"""

import json

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import config as cfg
import ollama_client as llm
from ratelimit import RateLimiter

app = Flask(__name__)
limiter = RateLimiter(cfg.RATE_LIMIT, cfg.RATE_WINDOW)

# синхронизируем URL/модель клиента с конфигом
llm.OLLAMA_URL = cfg.OLLAMA_URL
llm.DEFAULT_MODEL = cfg.MODEL


# ------------------------------------------------------------------
# Auth + rate limit (для защищённых эндпоинтов)
# ------------------------------------------------------------------

def _client_key() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.remote_addr or "anon"


def _authorize():
    """Вернуть (ошибка_response, статус) или None если всё ок."""
    if cfg.REQUIRE_AUTH:
        auth = request.headers.get("Authorization", "")
        key = auth[7:].strip() if auth.startswith("Bearer ") else ""
        if key not in cfg.API_KEYS:
            return jsonify({"error": "Неавторизовано. Укажите Authorization: Bearer <API_KEY>."}), 401
    ok, remaining, retry = limiter.check(_client_key())
    if not ok:
        resp = jsonify({"error": "Слишком много запросов (rate limit).",
                        "retry_after_sec": retry})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        return resp, 429
    return None


# ------------------------------------------------------------------
# Маршруты
# ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html",
                           require_auth=cfg.REQUIRE_AUTH, model=cfg.MODEL)


@app.route("/v1/health")
def health():
    up = llm.is_up()
    return jsonify({
        "status":    "ok" if up else "degraded",
        "ollama_up": up,
        "model":     cfg.MODEL,
        "models":    llm.list_models() if up else [],
        "limits": {
            "rate_limit":      f"{cfg.RATE_LIMIT}/{cfg.RATE_WINDOW}s",
            "max_input_chars": cfg.MAX_INPUT_CHARS,
            "max_history":     cfg.MAX_HISTORY,
            "num_ctx":         cfg.NUM_CTX,
        },
        "auth_required": cfg.REQUIRE_AUTH,
    })


@app.route("/v1/models")
def models():
    err = _authorize()
    if err:
        return err
    return jsonify({"models": llm.list_models()})


@app.route("/v1/chat", methods=["POST"])
def chat():
    err = _authorize()
    if err:
        return err
    if not llm.is_up():
        return jsonify({"error": "Локальная модель недоступна (Ollama не запущен)."}), 503

    data = request.get_json(force=True, silent=True) or {}
    # принимаем либо {message}, либо {messages:[...]}
    messages = data.get("messages")
    if not messages:
        msg = (data.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "Пустой запрос"}), 400
        messages = [{"role": "user", "content": msg}]

    # --- ограничение контекста ---
    if len(messages) > cfg.MAX_HISTORY:
        messages = messages[-cfg.MAX_HISTORY:]           # обрезаем историю
    total_chars = sum(len(m.get("content", "")) for m in messages)
    if total_chars > cfg.MAX_INPUT_CHARS:
        return jsonify({
            "error": f"Слишком длинный контекст: {total_chars} символов "
                     f"(лимит {cfg.MAX_INPUT_CHARS}).",
            "max_input_chars": cfg.MAX_INPUT_CHARS,
        }), 413

    model   = (data.get("model") or cfg.MODEL).strip()
    options = {"num_ctx": cfg.NUM_CTX, "num_predict": cfg.NUM_PREDICT}

    def generate():
        try:
            for part in llm.chat_stream(messages, model=model, options=options):
                if "token" in part:
                    yield json.dumps({"token": part["token"]}) + "\n"
                elif part.get("done"):
                    yield json.dumps({"done": True, "stats": part["stats"]}) + "\n"
        except Exception as e:
            yield json.dumps({"error": f"Ошибка модели: {e}"}) + "\n"

    return Response(stream_with_context(generate()),
                    mimetype="application/x-ndjson")


if __name__ == "__main__":
    # threaded=True — обрабатывать несколько запросов одновременно.
    # На проде запускать под gunicorn (см. Dockerfile / README).
    app.run(host="0.0.0.0", port=cfg.PORT, threaded=True)
