"""
Проверка веб-приложения на локальной LLM (без облака):
  • /health показывает, что локальный Ollama запущен и есть модели;
  • /ask стримит токены от локальной модели и отдаёт непустой ответ + метрики;
  • история сохраняется и очищается.

Требует запущенного Ollama с хотя бы одной моделью (см. week 6 / day 1).
"""

import json

import app as flask_app


def main() -> None:
    c = flask_app.app.test_client()

    h = c.get("/health").get_json()
    assert h["ollama_up"], "локальный Ollama не запущен"
    assert h["models"], "нет локальных моделей"
    print(f"✅ /health: Ollama запущен локально, модели: {h['models']}")

    r = c.post("/ask", json={"message": "Столица Японии?"})
    assert r.status_code == 200
    n_tokens, stats, answer = 0, None, ""
    for line in r.get_data(as_text=True).splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if "token" in obj:
            n_tokens += 1
            answer += obj["token"]
        elif obj.get("done"):
            stats = obj["stats"]
    assert answer.strip(), "пустой ответ модели"
    assert n_tokens > 1, "ответ не пришёл по стриму"
    assert stats and stats["eval_tokens"] > 0
    print(f"✅ /ask: стрим {n_tokens} чанков, ответ «{answer.strip()[:50]}…», "
          f"{stats['eval_tokens']} токенов за {stats['total_duration_ms']}мс")

    assert len(c.get("/history").get_json()) == 2
    print("✅ /history: диалог сохранён")
    c.post("/clear")
    assert len(c.get("/history").get_json()) == 0
    print("✅ /clear: история очищена")

    print("\n✅ Приложение работает на локальной LLM (offline, без облачных моделей)")


if __name__ == "__main__":
    main()
