"""
Классификация коммитов выбранной моделью реестра: собирает сообщения под режим модели, зовёт её по
OpenAI-совместимому API (llama-server или DeepSeek), разбирает JSON-ответ. Без Flask.
"""

from collections import Counter

import commit_types
import llm_client

DEEPSEEK_EXTRA = {"thinking": {"type": "disabled"}}


def classify_one(model: dict, message: str, api_key: str | None = None) -> dict:
    """Тип одного коммита: {type, strict, reply, seconds}; type=None, если ответ не разобрался."""
    if model["kind"] == "deepseek" and not (api_key or "").strip():
        raise ValueError("Для модели DeepSeek укажите deepseek_key.")
    res = llm_client.chat(model["url"], commit_types.build_messages(message, model["mode"]),
                          model=model.get("model", "local"), api_key=api_key if model["kind"] == "deepseek" else None,
                          max_tokens=commit_types.MAX_NEW_TOKENS,
                          extra=DEEPSEEK_EXTRA if model["kind"] == "deepseek" else None)
    pred, strict = commit_types.parse_type(res["content"])
    return {"type": pred, "strict": strict, "reply": res["content"], "seconds": res["seconds"]}


def classify_commits(model: dict, commits: list[dict], api_key: str | None = None) -> dict:
    """Типы для списка коммитов {subject, body, hash, ...}: по каждому, распределение и средняя задержка."""
    items = []
    for c in commits:
        message = c["subject"] + (f"\n\n{c['body']}" if c.get("body") else "")
        r = classify_one(model, message, api_key)
        items.append({"hash": c.get("hash"), "subject": c["subject"], "type": r["type"], "seconds": r["seconds"]})
    counts = Counter(i["type"] or "unknown" for i in items)
    return {"items": items, "by_type": dict(counts.most_common()),
            "avg_seconds": round(sum(i["seconds"] for i in items) / len(items), 4) if items else 0.0}
