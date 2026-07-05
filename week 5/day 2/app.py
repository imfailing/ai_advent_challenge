"""
Приложение: задаёт вопрос в ДВУХ режимах и показывает разницу.

Запуск:
    python app.py                       # демо-вопрос
    python app.py "ваш вопрос по базе"
"""

import sys

from rag import RagAgent

DEFAULT_Q = "Что происходит при попытке перепрыгнуть этап задачи?"


def main() -> None:
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_Q
    agent = RagAgent(strategy="structural")

    print(f"❓ {question}\n")

    print("─" * 68)
    print("БЕЗ RAG (только знания модели):")
    plain = agent.ask_plain(question)
    print(plain.answer)

    print("\n" + "─" * 68)
    print("С RAG (по базе документов):")
    rag = agent.ask_with_rag(question, k=4)
    print(rag.answer)
    print("\nИспользованные источники:")
    for s in rag.sources:
        print(f"  • {s['file']} → {s['section'][:40]}  (score {s['score']})")


if __name__ == "__main__":
    main()
