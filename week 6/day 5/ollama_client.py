"""
Клиент локальной LLM (Ollama). Только stdlib — никаких облачных SDK.

Сервер Ollama работает локально на http://localhost:11434.
Используем нативный /api/chat (со стримингом токенов) и /api/tags (модели).
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"


def is_up() -> bool:
    """Доступен ли локальный сервер Ollama."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=3) as r:
            json.load(r)
        return True
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
            data = json.load(r)
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def chat_stream(messages: list[dict], model: str = DEFAULT_MODEL,
                options: dict | None = None) -> Iterator[dict]:
    """
    Стриминг ответа локальной модели.
    Отдаёт по кусочкам: {"token": "..."} и в конце {"done": True, "stats": {...}}.

    options — параметры инференса Ollama: temperature, num_predict (макс токенов
    ответа), num_ctx (окно контекста), top_p, repeat_penalty и т.п.
    """
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("done"):
                yield {"done": True, "stats": {
                    "prompt_tokens":     chunk.get("prompt_eval_count", 0),
                    "eval_tokens":       chunk.get("eval_count", 0),
                    "total_duration_ms": round(chunk.get("total_duration", 0) / 1e6),
                }}
            else:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield {"token": token}


def chat(messages: list[dict], model: str = DEFAULT_MODEL,
         options: dict | None = None) -> str:
    """Нестриминговый ответ целиком."""
    return chat_full(messages, model, options)[0]


def chat_full(messages: list[dict], model: str = DEFAULT_MODEL,
              options: dict | None = None) -> tuple[str, dict]:
    """Ответ целиком + метрики (eval_tokens, total_duration_ms)."""
    out, stats = [], {}
    for part in chat_stream(messages, model, options):
        if "token" in part:
            out.append(part["token"])
        elif part.get("done"):
            stats = part["stats"]
    return "".join(out), stats
