"""
Пайплайн индексации: загрузка → chunking → эмбеддинги → сохранение индекса.

Запуск:
    python build_index.py fixed
    python build_index.py structural
    python build_index.py both        # обе стратегии
"""

import sys

import chunking
import index_store
import loader
from embedder import Embedder

CORPUS = "corpus"


def build(strategy: str, embedder: Embedder) -> dict:
    docs   = loader.load_corpus(CORPUS)
    chunks = chunking.chunk_corpus(docs, strategy)
    print(f"[{strategy}] документов: {len(docs)}, чанков: {len(chunks)} — считаю эмбеддинги…")
    embeddings = embedder.embed([c["text"] for c in chunks])
    stats = index_store.build(chunks, embeddings, strategy)
    print(f"[{strategy}] индекс сохранён: {stats['chunks']} чанков "
          f"(ср. {stats['avg_chars']} симв., min {stats['min_chars']}, max {stats['max_chars']}), "
          f"манифест {stats['json']}, эмбеддинги → index.db")
    return stats


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "both"
    strategies = ["fixed", "structural"] if arg == "both" else [arg]
    for s in strategies:
        if s not in chunking.STRATEGIES:
            print(f"Неизвестная стратегия: {s}. Доступно: fixed, structural, both")
            sys.exit(1)
    embedder = Embedder()
    for s in strategies:
        build(s, embedder)
    print("Готово ✓")


if __name__ == "__main__":
    main()
