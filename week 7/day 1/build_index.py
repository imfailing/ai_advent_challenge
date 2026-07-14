"""
Индексация документации проекта: docs → chunking → эмбеддинги → SQLite-индекс.

Запуск:
    python build_index.py
"""

import chunking
import index_store
from embedder import Embedder
from project_loader import load_project_docs

STRATEGY = "structural"


def main() -> None:
    docs = load_project_docs()
    chunks = chunking.chunk_corpus(docs, STRATEGY)
    print(f"Документов: {len(docs)}, чанков: {len(chunks)} — считаю эмбеддинги…")
    embeddings = Embedder().embed([c["text"] for c in chunks])
    stats = index_store.build(chunks, embeddings, STRATEGY)
    print(f"Индекс сохранён: {stats['chunks']} чанков "
          f"(ср. {stats['avg_chars']} симв.), эмбеддинги → index.db")


if __name__ == "__main__":
    main()
