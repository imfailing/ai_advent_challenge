"""
Сравнение качества ответов БЕЗ RAG и С RAG на 10 контрольных вопросах.

Для каждого вопроса:
  • plain — ответ модели без контекста;
  • rag   — ответ модели по найденным чанкам.
Метрики:
  • keyword hit — доля ожидаемых ключевых фактов, попавших в ответ;
  • pass        — hit ≥ 0.5 (ответ по сути верный);
  • source recall (только rag) — найден ли хотя бы один ожидаемый источник.
"""

import os

from eval_set import EVAL
from rag import RagAgent


def keyword_hit(answer: str, expected: list[str]) -> float:
    low = answer.lower()
    hits = sum(1 for kw in expected if kw.lower() in low)
    return hits / len(expected) if expected else 0.0


def source_recall(sources: list[dict], expected: list[str]) -> bool:
    files = {s["file"] for s in sources}
    return any(e in files for e in expected)


def main() -> None:
    agent = RagAgent(strategy="structural")

    plain_pass = rag_pass = src_ok = 0
    rows = []

    for i, item in enumerate(EVAL, 1):
        q = item["question"]
        print(f"[{i}/10] {q}")

        plain = agent.ask_plain(q)
        rag   = agent.ask_with_rag(q, k=4)

        h_plain = keyword_hit(plain.answer, item["expected"])
        h_rag   = keyword_hit(rag.answer,   item["expected"])
        p_plain = h_plain >= 0.5
        p_rag   = h_rag   >= 0.5
        recall  = source_recall(rag.sources, item["expected_sources"])

        plain_pass += p_plain
        rag_pass   += p_rag
        src_ok     += recall

        rows.append((i, h_plain, p_plain, h_rag, p_rag, recall,
                     [s["file"] for s in rag.sources]))
        print(f"      без RAG: hit={h_plain:.0%} {'✓' if p_plain else '✗'}   "
              f"с RAG: hit={h_rag:.0%} {'✓' if p_rag else '✗'}   "
              f"источники {'✓' if recall else '✗'}")

    print("\n" + "=" * 70)
    print("  СВОДКА")
    print("=" * 70)
    print(f"{'#':>3}  {'без RAG':>10}  {'с RAG':>10}  {'источники':>10}")
    print("-" * 70)
    for i, hp, pp, hr, pr, rc, _ in rows:
        print(f"{i:>3}  {hp:>9.0%}{'✓' if pp else '✗'}  "
              f"{hr:>9.0%}{'✓' if pr else '✗'}  {'✓' if rc else '✗':>10}")
    print("-" * 70)
    print(f"Верных ответов (pass): без RAG {plain_pass}/10, с RAG {rag_pass}/10")
    print(f"Source recall (нужный источник найден): {src_ok}/10")

    print("\n" + "=" * 70)
    print("  ВЫВОД")
    print("=" * 70)
    print(f"• Без RAG модель не знает специфику проекта → {plain_pass}/10 верных.")
    print(f"• С RAG ответы опираются на корпус → {rag_pass}/10 верных "
          f"(+{rag_pass - plain_pass}).")
    print(f"• В {src_ok}/10 случаев среди найденных чанков был нужный источник.")


if __name__ == "__main__":
    main()
