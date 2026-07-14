"""
Проверка ассистента разработчика:
  • индекс документации проекта собран (README + доки дней + claude/);
  • /help показывает справку;
  • вопрос о структуре — отвечает по документации (RAG) с источниками;
  • вопрос про git — вызывает MCP-инструмент (как минимум git_branch);
  • веб-интерфейс отвечает (через test_client).

Нужен DEEPSEEK_API_KEY и построенный индекс (python build_index.py).
"""

import app as flask_app
import index_store


def main() -> None:
    assert index_store.count("structural") > 50, "индекс не построен: python build_index.py"
    print(f"✅ индекс документации: {index_store.count('structural')} чанков")

    c = flask_app.app.test_client()
    assert c.get("/").status_code == 200
    print("✅ веб-интерфейс отвечает (GET /)")

    # /help
    r = c.post("/ask", json={"message": "/help"}).get_json()
    assert r.get("help") and "ассистент" in r["answer"].lower()
    print("✅ /help — показывает справку")

    # структура проекта (RAG)
    r = c.post("/ask", json={"message": "Какие недели есть в проекте и про что они?"}).get_json()
    assert r["sources"], "нет источников из документации"
    files = {s["source"] for s in r["sources"]}
    assert any("README" in f or "claude" in f or "week" in f for f in files), files
    assert "week" in r["answer"].lower() or "недел" in r["answer"].lower()
    print(f"✅ вопрос о структуре: ответ по докам, источники {sorted(files)[:3]}")

    # git через MCP
    r = c.post("/ask", json={"message": "На какой git-ветке сейчас проект?"}).get_json()
    tools = [g["tool"] for g in r["git_calls"]]
    assert "git_branch" in tools, f"git_branch не вызван: {tools}"
    assert "main" in r["answer"].lower() or "main" in str(r["git_calls"]).lower()
    print(f"✅ вопрос про git: вызван MCP {tools}, ветка определена")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — ассистент понимает проект")


if __name__ == "__main__":
    main()
