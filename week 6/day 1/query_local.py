"""
Обращение к локальной LLM (Ollama) через HTTP API.

Ollama поднимает локальный сервер на http://localhost:11434 и предоставляет
OpenAI-совместимый эндпоинт /v1/chat/completions, а также нативный /api/chat.
Здесь используем нативный /api/chat (без внешних зависимостей — только stdlib).

Запускаем 3 запроса разной сложности:
  1. простой факт;
  2. рассуждение / логика;
  3. генерация кода.

Запуск:
    python query_local.py
    python query_local.py "свой вопрос"
"""

import json
import sys
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:1.5b"


def version() -> str:
    with urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=5) as r:
        return json.load(r)["version"]


def chat(prompt: str, model: str = MODEL) -> dict:
    """Один запрос к локальной модели. Возвращает ответ + метрики."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    elapsed = round(time.perf_counter() - started, 2)
    return {
        "answer":       data["message"]["content"],
        "elapsed_sec":  elapsed,
        "eval_count":   data.get("eval_count", 0),          # токенов сгенерировано
        "prompt_count": data.get("prompt_eval_count", 0),   # токенов промпта
    }


QUERIES = [
    ("простой факт",
     "Столица Франции — назови одним словом."),
    ("рассуждение / логика",
     "В комнате 3 кота. Каждый кот видит 2 других котов. "
     "Сколько всего котов? Объясни рассуждение кратко."),
    ("генерация кода",
     "Напиши функцию на Python, которая возвращает список простых чисел "
     "до N включительно. Только код."),
]


def main() -> None:
    print(f"Ollama сервер: v{version()}  ·  модель: {MODEL}\n")

    if len(sys.argv) > 1:
        r = chat(" ".join(sys.argv[1:]))
        print(r["answer"])
        print(f"\n[{r['eval_count']} токенов, {r['elapsed_sec']} с]")
        return

    for i, (label, prompt) in enumerate(QUERIES, 1):
        print("─" * 70)
        print(f"[{i}/3] {label}")
        print(f"❓ {prompt}")
        r = chat(prompt)
        print(f"🤖 {r['answer'].strip()}")
        print(f"   [{r['prompt_count']}→{r['eval_count']} токенов · {r['elapsed_sec']} с]\n")


if __name__ == "__main__":
    main()
