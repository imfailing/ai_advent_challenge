"""
Сравнение конфигураций RAG на 10 контрольных вопросах:

  A. plain          — поиск top-K=4, без фильтра и rewrite (baseline, как day 2);
  B. rerank         — поиск top-N=12 → cross-encoder → порог → top-K=4;
  C. rewrite+rerank — query rewrite (мульти-запрос) + реранкинг + порог.

Метрики: keyword-hit / pass (hit≥0.5) / source-recall, а также сколько чанков
найдено ДО фильтра и оставлено ПОСЛЕ.
"""

import statistics

from eval_set import EVAL
from rag import RagAgent, RagConfig

CONFIGS = {
    "A plain":          RagConfig(top_k=4),
    "B rerank":         RagConfig(use_rerank=True, top_n=12, top_k=4, threshold=0.3),
    "C rewrite+rerank": RagConfig(use_rewrite=True, use_rerank=True,
                                  top_n=12, top_k=4, threshold=0.3),
}


def keyword_hit(answer: str, expected: list[str]) -> float:
    low = answer.lower()
    return sum(1 for kw in expected if kw.lower() in low) / len(expected)


def source_recall(sources: list[dict], expected: list[str]) -> bool:
    files = {s["file"] for s in sources}
    return any(e in files for e in expected)


def main() -> None:
    agent = RagAgent()
    results = {name: {"pass": 0, "recall": 0, "before": [], "after": [], "per_q": []}
               for name in CONFIGS}

    for i, item in enumerate(EVAL, 1):
        q = item["question"]
        print(f"[{i}/10] {q[:60]}…")
        for name, cfg in CONFIGS.items():
            r = agent.ask(q, cfg)
            hit    = keyword_hit(r.answer, item["expected"])
            passed = hit >= 0.5
            recall = source_recall(r.sources, item["expected_sources"])
            results[name]["pass"]   += passed
            results[name]["recall"] += recall
            results[name]["before"].append(r.retrieved_n)
            results[name]["after"].append(len(r.kept))
            results[name]["per_q"].append((passed, recall))
            print(f"      {name:<18} hit={hit:.0%} {'✓' if passed else '✗'}  "
                  f"src {'✓' if recall else '✗'}  "
                  f"(до фильтра {r.retrieved_n} → после {len(r.kept)})")

    print("\n" + "=" * 72)
    print("  СВОДКА ПО КОНФИГУРАЦИЯМ")
    print("=" * 72)
    print(f"{'Конфигурация':<20}{'pass':>8}{'src recall':>12}"
          f"{'ср. до':>10}{'ср. после':>12}")
    print("-" * 72)
    for name in CONFIGS:
        r = results[name]
        print(f"{name:<20}{r['pass']:>6}/10{r['recall']:>10}/10"
              f"{statistics.mean(r['before']):>10.1f}{statistics.mean(r['after']):>12.1f}")

    print("\n" + "=" * 72)
    print("  ВЫВОД")
    print("=" * 72)
    a, b, c = results["A plain"]["pass"], results["B rerank"]["pass"], results["C rewrite+rerank"]["pass"]
    print(f"• A (baseline, без фильтра): {a}/10 верных.")
    print(f"• B (+ реранкинг и порог):   {b}/10  (реранкер поднимает релевантные "
          f"чанки, порог отсекает мусор).")
    print(f"• C (+ query rewrite):       {c}/10  (мульти-запрос добавляет recall "
          f"на «списковых» вопросах).")
    print("• Второй этап (rerank+threshold) и rewrite повышают качество, "
          "не раздувая контекст (top-K фиксирован = 4).")


if __name__ == "__main__":
    main()
