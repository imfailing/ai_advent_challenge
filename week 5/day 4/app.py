"""
Приложение: структурированный RAG-ответ (ответ + источники + цитаты)
и режим «не знаю» при слабом контексте.

Запуск:
    python app.py
    python app.py "ваш вопрос"
"""

import sys

from rag import RagAgent, RagConfig

DEFAULT_Q = "Что происходит при попытке перепрыгнуть этап задачи?"


def main() -> None:
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_Q
    agent = RagAgent()
    r = agent.ask(question, RagConfig())

    print(f"❓ {question}\n")

    if not r.know:
        print(f"🤷 НЕ ЗНАЮ (релевантность {r.top_score} ниже порога)")
        print(f"   {r.clarification}")
        return

    print(f"🤖 ОТВЕТ:\n   {r.answer}\n")

    print("📎 ИСТОЧНИКИ:")
    for s in r.sources:
        print(f"   • {s.get('source')} → {s.get('section')}  [{s.get('chunk_id')}]")

    print("\n💬 ЦИТАТЫ:")
    for q in r.quotes:
        mark = "✓" if q["grounded"] else "✗ (не найдена дословно)"
        print(f"   {mark} [{q['chunk_id']}]")
        print(f"      «{q['text'][:120]}»")

    print(f"\n(режим {r.mode}, релевантность top {r.top_score})")


if __name__ == "__main__":
    main()
