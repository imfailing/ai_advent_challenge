"""
Сравнение двух стратегий chunking: fixed vs structural.

Метрики:
  1. Структурные — число чанков, средний/мин/макс размер, разброс (std).
  2. Качество ретрива — на наборе запросов для каждой стратегии берём top-3,
     считаем средний косинус top-1 и top-3 + показываем, из какого раздела
     (section) пришёл лучший чанк (читаемость метки — плюс structural).

Перед запуском убедитесь, что индексы построены: python build_index.py both
"""

import statistics

import index_store
import loader
import chunking
from embedder import Embedder

QUERIES = [
    "как работает валидация переходов между этапами задачи",
    "сжатие контекста и суммаризация истории диалога",
    "запуск MCP-сервера и список инструментов",
    "подсчёт токенов и стоимости запроса",
    "фоновый планировщик и периодический сбор метрик",
]

STRATS = ["fixed", "structural"]


def structural_metrics() -> dict:
    docs = loader.load_corpus("corpus")
    out = {}
    for s in STRATS:
        sizes = [c["n_chars"] for c in chunking.chunk_corpus(docs, s)]
        out[s] = {
            "chunks": len(sizes),
            "avg":    round(statistics.mean(sizes)),
            "min":    min(sizes),
            "max":    max(sizes),
            "std":    round(statistics.pstdev(sizes)),
        }
    return out


def retrieval_quality(embedder: Embedder) -> dict:
    qvecs = embedder.embed(QUERIES)
    out = {s: {"top1": [], "top3": [], "examples": []} for s in STRATS}
    for q, qv in zip(QUERIES, qvecs):
        for s in STRATS:
            hits = index_store.search(qv, s, k=3)
            if not hits:
                continue
            out[s]["top1"].append(hits[0]["score"])
            out[s]["top3"].append(statistics.mean(h["score"] for h in hits))
            out[s]["examples"].append((q, hits[0]))
    for s in STRATS:
        out[s]["avg_top1"] = round(statistics.mean(out[s]["top1"]), 3)
        out[s]["avg_top3"] = round(statistics.mean(out[s]["top3"]), 3)
    return out


def main() -> None:
    if index_store.count("fixed") == 0 or index_store.count("structural") == 0:
        print("Индексы не найдены. Сначала: python build_index.py both")
        return

    sm = structural_metrics()
    embedder = Embedder()
    rq = retrieval_quality(embedder)

    print("=" * 68)
    print("  СРАВНЕНИЕ СТРАТЕГИЙ CHUNKING")
    print("=" * 68)
    print(f"{'Метрика':<28}{'fixed':>18}{'structural':>18}")
    print("-" * 68)
    rows = [
        ("Число чанков",        "chunks"),
        ("Средний размер, симв", "avg"),
        ("Мин размер",          "min"),
        ("Макс размер",         "max"),
        ("Разброс (std)",       "std"),
    ]
    for label, key in rows:
        print(f"{label:<28}{sm['fixed'][key]:>18}{sm['structural'][key]:>18}")
    print(f"{'Ретрив: ср. косинус top-1':<28}{rq['fixed']['avg_top1']:>18}{rq['structural']['avg_top1']:>18}")
    print(f"{'Ретрив: ср. косинус top-3':<28}{rq['fixed']['avg_top3']:>18}{rq['structural']['avg_top3']:>18}")

    print("\n--- Лучший чанк по запросам (section-метка) ---")
    for i, q in enumerate(QUERIES):
        print(f"\nЗапрос: «{q}»")
        for s in STRATS:
            _, hit = rq[s]["examples"][i]
            print(f"  {s:<11} score={hit['score']:.3f}  {hit['file']} → «{hit['section'][:38]}»")

    print("\n" + "=" * 68)
    print("  ВЫВОД")
    print("=" * 68)
    better = "structural" if rq["structural"]["avg_top3"] >= rq["fixed"]["avg_top3"] else "fixed"
    print(f"• Fixed: равномерные чанки (~{sm['fixed']['avg']} симв., std {sm['fixed']['std']}), "
          f"но метки разделов безликие (fixed[i]) и режут контекст на границах.")
    print(f"• Structural: осмысленные section (заголовки/функции), разброс больше "
          f"(std {sm['structural']['std']}), чанки семантически цельные.")
    print(f"• По среднему косинусу top-3 лучше: {better} "
          f"(fixed {rq['fixed']['avg_top3']} vs structural {rq['structural']['avg_top3']}).")
    print("• Для навигации и цитирования удобнее structural — у чанков понятные метки.")


if __name__ == "__main__":
    main()
