"""
Клиент LLM-шлюза (week 10 / day 3): все вызовы модели из цикла идут только через него.

Роль в цикле: отправляет сообщения в `POST /chat` (профиль `code`, режим `mask`), разбирает ответ и
возвращает решение шлюза: что он сделал с входом (allowed/masked/blocked, находки без секретов) и с
выходом (allowed/masked/blocked). Напрямую в модель этот код не ходит. При 429 ждёт `Retry-After`.
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_URL = "http://127.0.0.1:5013/chat"


@dataclass(frozen=True)
class Reply:
    """Ответ шлюза: текст и решения guard'ов."""

    ok: bool
    content: str = ""
    error: str = ""
    request_id: str = ""
    input_action: str = ""  # allowed | masked | blocked
    input_findings: list[dict] = field(default_factory=list)
    output_action: str = ""  # allowed | masked | blocked
    output_findings: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def ask(messages: list[dict], *, url: str = DEFAULT_URL, mode: str = "mask", profile: str = "code",
        max_tokens: int = 12000, timeout: int = 1800, retries: int = 3, thinking: bool = True) -> Reply:
    """Отправить сообщения в шлюз; вернуть решение шлюза и ответ модели."""
    body = json.dumps({"messages": messages, "mode": mode, "profile": profile, "max_tokens": max_tokens,
                       "thinking": thinking}).encode()
    for _ in range(retries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — шлюз в локальной сети
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode() or "{}")
            if e.code == 429:
                time.sleep(int(data.get("retry_after") or 60))
                continue
            findings = data.get("findings") or []
            return Reply(False, error=data.get("error") or f"шлюз вернул {e.code}", request_id=data.get("request_id", ""),
                         input_action="blocked" if findings else "", input_findings=findings)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return Reply(False, error=f"шлюз недоступен: {e}")
        guard = data.get("guard") or {}
        usage = data.get("usage") or {}
        return Reply(True, content=data.get("content", ""), request_id=data.get("request_id", ""),
                     input_action=guard.get("input", ""), input_findings=guard.get("input_findings") or [],
                     output_action=guard.get("output", ""), output_findings=guard.get("output_findings") or [],
                     prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0),
                     cost_usd=float(data.get("cost_usd") or 0.0))
    return Reply(False, error="шлюз вернул 429 несколько раз подряд")
