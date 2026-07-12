"""
Сравнение локальной и облачной генерации в одном RAG-пайплайне.

Retrieval одинаковый и ЛОКАЛЬНЫЙ для обоих. Отличается только генератор:
  local — qwen2.5:1.5b через Ollama (офлайн);
  cloud — deepseek-v4-flash (если есть DEEPSEEK_API_KEY).

Оцениваем на 10 контрольных вопросах:
  • качество     — доля ожидаемых ключевых фактов в ответе (keyword hit / pass);
  • скорость     — время генерации (retrieval общий);
  • стабильность — доля непустых корректных ответов, разброс времени.

Запуск:
    python compare.py           # local + cloud (если есть ключ)
    python compare.py local     # только локально
"""

import os
import statistics
import sys

from eval_set import EVAL
from rag import LocalRAG


def keyword_hit(answer: str, expected: list[str]) -> float:
    low = answer.lower()
    return sum(1 for kw in expected if kw.lower() in low) / len(expected)


def run_backend(agent: LocalRAG, backend: str) -> dict:
    passes, hits, gen_times, empties = 0, [], [], 0
    print(f"\n{'='*72}\n  БЭКЕНД: {backend.upper()}\n{'='*72}")
    for i, item in enumerate(EVAL, 1):
        r = agent.ask(item["question"], backend=backend)
        hit = keyword_hit(r.answer, item["expected"])
        passed = hit >= 0.5
        passes += passed
        hits.append(hit)
        gen_times.append(r.generate_sec)
        if not r.answer.strip():
            empties += 1
        print(f"  [{i:>2}] hit={hit:.0%} {'✓' if passed else '✗'}  "
              f"ген {r.generate_sec:>5.2f}с  {r.eval_tokens:>4}ток  | "
              f"{r.answer.strip()[:70].replace(chr(10),' ')}…")
    return {
        "backend":   backend,
        "pass":      passes,
        "avg_hit":   round(statistics.mean(hits), 2),
        "avg_gen":   round(statistics.mean(gen_times), 2),
        "max_gen":   round(max(gen_times), 2),
        "std_gen":   round(statistics.pstdev(gen_times), 2),
        "empties":   empties,
    }


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    agent = LocalRAG()

    backends = ["local"]
    if only == "local":
        pass
    elif os.environ.get("DEEPSEEK_API_KEY"):
        backends.append("cloud")
    else:
        print("(DEEPSEEK_API_KEY не задан — только локальный бэкенд)")

    results = [run_backend(agent, b) for b in backends]

    print("\n" + "=" * 72)
    print("  СРАВНЕНИЕ  (retrieval локальный для обоих)")
    print("=" * 72)
    print(f"{'Бэкенд':<10}{'верных':>10}{'ср.hit':>9}{'ср.ген,с':>11}"
          f"{'макс,с':>9}{'разброс':>9}{'пустых':>9}")
    print("-" * 72)
    for r in results:
        print(f"{r['backend']:<10}{r['pass']:>8}/10{r['avg_hit']:>9.0%}"
              f"{r['avg_gen']:>11.2f}{r['max_gen']:>9.2f}{r['std_gen']:>9.2f}{r['empties']:>9}")

    print("\n" + "=" * 72)
    print("  ОЦЕНКА")
    print("=" * 72)
    loc = next(r for r in results if r["backend"] == "local")
    print(f"• Качество:     локальная {loc['pass']}/10 верных (ср. hit {loc['avg_hit']:.0%}).")
    print(f"• Скорость:     локальная генерация ~{loc['avg_gen']}с (макс {loc['max_gen']}с), офлайн.")
    print(f"• Стабильность: пустых ответов {loc['empties']}/10, разброс времени {loc['std_gen']}с.")
    if len(results) > 1:
        cl = next(r for r in results if r["backend"] == "cloud")
        print(f"• Облако:       {cl['pass']}/10 верных, ср. hit {cl['avg_hit']:.0%}, "
              f"ген ~{cl['avg_gen']}с.")
        dq = cl["pass"] - loc["pass"]
        print(f"• Итог: облако {'точнее' if dq>0 else 'наравне' if dq==0 else 'слабее'} "
              f"(+{dq} pass); локальная — офлайн, без ключей, сопоставимая скорость на 1.5B.")


if __name__ == "__main__":
    main()
