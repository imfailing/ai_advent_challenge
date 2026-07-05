"""
Приложение: показывает второй этап RAG — реранкинг + фильтр по порогу +
query rewrite. Наглядно видно top-K ДО и ПОСЛЕ фильтрации.

Запуск:
    python app.py
    python app.py "ваш вопрос"
"""

import sys

from rag import RagAgent, RagConfig

DEFAULT_Q = "Какие три стратегии управления контекстом реализованы?"


def show(title: str, r) -> None:
    print("─" * 70)
    print(title)
    if r.queries and len(r.queries) > 1:
        print("  запросы (rewrite):")
        for q in r.queries:
            print(f"    • {q}")
    print(f"  найдено до фильтра: {r.retrieved_n}  →  оставлено: {len(r.kept)}"
          f"  (отсеяно: {len(r.dropped)})")
    print("  чанки в контексте:")
    for s in r.sources:
        rr = f", rerank {s['rerank']}" if s["rerank"] is not None else ""
        print(f"    ✓ {s['file']} → {s['section'][:34]}  (sim {s['score']}{rr})")
    if r.dropped:
        print("  примеры отсеянных:")
        for c in r.dropped[:3]:
            rr = f"rerank {c['rerank']:.3f}" if "rerank" in c else f"sim {c['score']:.3f}"
            print(f"    ✗ {c['file']} → {c['section'][:30]}  ({rr})")
    print(f"\n  🤖 {r.answer}\n")


def main() -> None:
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_Q
    agent = RagAgent()
    print(f"❓ {question}\n")

    show("БЕЗ ФИЛЬТРА (baseline: top-K=4, без rerank/rewrite)",
         agent.ask(question, RagConfig(top_k=4)))

    show("С ФИЛЬТРОМ (rewrite + rerank cross-encoder + порог 0.3 → top-K=4)",
         agent.ask(question, RagConfig(use_rewrite=True, use_rerank=True,
                                       top_n=12, top_k=4, threshold=0.3)))


if __name__ == "__main__":
    main()
