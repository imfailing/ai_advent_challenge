"""
Клиент апстрима: пересылка запроса в локальную LLM (llama.cpp, OpenAI-совместимый API).

Роль в сервисе: единственное место, где шлюз ходит в сеть. Адрес и ключ апстрима хранятся
на стороне шлюза (`LLAMA_BASE_URL`, `LLAMA_API_KEY`): клиент шлюза их не видит и не передаёт —
в этом смысл прокси. Ошибки апстрима превращаются в `UpstreamError` с русским текстом.
"""

import json
import os
import urllib.error
import urllib.request

MODEL = "qwen3.5-122b"


class UpstreamError(Exception):
    """Апстрим недоступен или вернул ошибку."""


def complete(messages: list[dict], max_tokens: int, timeout: int = 900) -> dict:
    """Отправить диалог в апстрим; вернуть {"content", "model", "prompt_tokens", "completion_tokens"}."""
    key = os.environ.get("LLAMA_API_KEY", "")
    base_url = os.environ.get("LLAMA_BASE_URL", "").rstrip("/")
    if not key or not base_url:
        raise UpstreamError("Шлюз не настроен: задайте LLAMA_API_KEY и LLAMA_BASE_URL на стороне сервера.")
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — свой сервер в LAN
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise UpstreamError(f"Апстрим вернул ошибку {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpstreamError("Апстрим недоступен или не ответил вовремя.") from e
    usage = data.get("usage") or {}
    return {
        "content": (data["choices"][0]["message"].get("content") or "").strip(),
        "model": data.get("model") or MODEL,
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }
